from email.mime.text import MIMEText
from email.utils import formatdate

import os
import time
from random import randint

import requests
from bs4 import BeautifulSoup
import smtplib

# TODO: This isn't hard coded but the handling of denver/boulder is
URLS = {'Denver': 'https://denver.craigslist.org/d/free-stuff/search/zip',
        'Boulder': 'https://boulder.craigslist.org/d/free-stuff/search/zip'}

# Need more keywords?
KEYWORDS = [
'tv', 'television', 'computer', 'electronic', 'calculator',
'vintage', 'electric', 'chinchilla', 'router', 'modem', 'printer',
 'scanner', 'copier', 'sound'
]


class Cache:
    def __init__(self, source):
        self.count = 0
        self.max = 250
        self.source = source
        self.cache_set = set()
        self.seen = []

    def add_entry(self, url, log_file):
        if url in self.cache_set:
            log_file.write('Already in cache "{}"'.format(url) + '\n')
            return False

        next_index = self.count % self.max

        # We've filled the cache and will be replacing an entry
        if self.count > self.max:
            entry_to_remove = self.seen[next_index]
            self.cache_set.remove(entry_to_remove)

        # Add next item to cache, overriding entry in list if applicable
        self.cache_set.add(url)

        if len(self.seen) > next_index:
            self.seen[next_index] = url
        else:
            self.seen.append(url)

        self.count += 1

        log_file.write('Added "{}" to cache'.format(url) + '\n')

        return True


def parse_results(table, cache, log_file):
    interesting_entries = {}

    for li in table.find_all('li'):

        try:
            title_wrapper = li.find_all('p', class_='result-info')[0]
            title_text = title_wrapper.find_all('a', class_='result-title')[0].contents[0].string
            title_image_url = '' # TODO: Images are dynamically loaded with ajax, so we'd need a more complex script to grab them
            title_url = title_wrapper.a.get('href', '')
        except IndexError:
            continue

        title_text = title_text.replace(',', '').replace('.', '').replace('!', '').replace('?', '').lower()
        title_url = title_url.replace('https://', '')
        title_image_url = title_image_url.replace('https://', '')

        for word in KEYWORDS:
            if word in title_text and cache.add_entry(title_url, log_file):
                interesting_entries[title_text] = {'url': title_url, 'img': title_image_url}

    return interesting_entries, cache


def send_mail(source, entries):
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.login('paul@gerlich.io', os.environ['GMAIL_PASSWORD'])

    for key, info in entries.iteritems():
        msg = '{}:\n{} : {}\n {}'.format(source, key, info['url'], info['img'])

        message = MIMEText(msg)
        message['Date'] = formatdate()
        message['From'] = 'paul@gerlich.io'

        server.sendmail('paul@gerlich.io', os.environ['RECIPIENT'], message.as_string())

    server.close()


def lambda_handler(event, context):
    """ Code that was going to be a lambda function but isn't

    Grabs results form Denver/Boulder "free" listings and texts anything that meets certain criteria to my cell phone

    :param event: 
    :param context: 
    :return: 
    """
    denver_cache = Cache('Denver')
    boulder_cache = Cache('Boulder')

    while True:

	log_file = open("log.txt", "a")

        # Hit craiglist denver / boulder for free stuff, apply user agent
        # TODO: Always use the same quotes
        for source, url in URLS.iteritems():
            # Request
            log_file.write("Requesting from {}..".format(source) + '\n')
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
            response = requests.get(url, headers=headers)

            # Parse
            log_file.write("Parsing" + '\n')
            beautiful_soup = BeautifulSoup(response.text)
            results_table = beautiful_soup.find_all('ul', class_='rows')

            if not results_table:
                continue

	    # TODO: Store cache and url in a dictionary keyd by source name so that this could be generic and in a loop
            interesting = {}
            if source == 'Denver':
                interesting, denver_cache = parse_results(results_table[0], denver_cache, log_file)

                log_file.write("{} cache count is now {}".format(source, denver_cache.count) + '\n')

                # Send texts
                if interesting:
                    log_file.write("Sending texts for {} interesting items in {}".format(len(interesting.keys()), source) + '\n')
                    send_mail(source, interesting)

            if source == 'Boulder':
                interesting, boulder_cache = parse_results(results_table[0], boulder_cache, log_file)

                # Send texts
                if interesting:
                    log_file.write("Sending texts for {} interesting items in {}".format(len(interesting.keys()), source) + '\n')
                    send_mail(source, interesting)

                log_file.write("{} cache count is now {}".format(source, boulder_cache.count) + '\n')

        sleep_time = randint(120, 240)
        log_file.write("Sleeping for {} seconds".format(sleep_time) + '\n')
        log_file.close()
        time.sleep(sleep_time)


lambda_handler({}, None)

