import os
import smtplib
import time
import datetime
from email.mime.text import MIMEText
from email.utils import formatdate
from random import randint

import requests
from bs4 import BeautifulSoup


class Cache:
    """ Cache used to store craigslist results keyed by their URL
    """
    def __init__(self, service, max=250):
        self.count = 0
        self.max = max
        self.service = service
        self.cache_set = set()
        self.seen = []

    def add_entry(self, title, url, log_file):
        """ Adds an entry to the cache

        Args:
            url: String url for the add
            title: String title of the article
            log_file: File to write log statements to

        Returns:
            Whether or not the entry was added

        """
        if url in self.cache_set:
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

        log_file.write('{}: Added {} to cache. Size is now:'.format(self.service, title, self.count) + '\n')

        return True


class CraigslistWatcher:
    """ Used to watch craigslist postings for free stuff """

    def __init__(self, services, keywords):
        # Default service
        self.services = services or ['denver', 'boulder']

        # Base url for all craigslist free postings
        self.base_url = 'https://{}.craigslist.org/d/free-stuff/search/zip'

        # Default keywords we're interested in
        self.keywords = keywords or [
            'tv', 'television', 'computer', 'electronic', 'calculator',
            'vintage', 'electric', 'chinchilla', 'router', 'modem', 'printer',
            'scanner', 'copier', 'sound', 'free', 'plant'
        ]

        # Create cache for each service provided
        self.caches = {service: Cache(service)
                  for service in self.services}


    def parse_results(self, table, cache, log_file):
        """ Use beautiful soup to parse out each entry and add them to the cache

        Args:
            table: BeautifulSoup.DomElement representing the entries
            cache: Cache for this service
            log_file: File to write logs to

        Returns:
            A tuple containing (entries matching our keyword criteria, updated cache)
        """
        interesting_entries = {}

        for li in table.find_all('li'):

            try:
                title_wrapper = li.find_all('p', class_='result-info')[0]
                title_text = title_wrapper.find_all('a', class_='result-title')[0].contents[0].string
                title_image_url = ''  # TODO: Images are dynamically loaded with ajax, so we'd need a more complex script to grab them
                title_url = title_wrapper.a.get('href', '')
            except IndexError:
                continue

            title_text = title_text.replace(',', '').replace('.', '').replace('!', '').replace('?', '').lower()
            title_url = title_url.replace('https://', '')
            title_image_url = title_image_url.replace('https://', '')

            for word in self.keywords:
                if word in title_text and cache.add_entry(title_text, title_url, log_file):
                    interesting_entries[title_text] = {'url': title_url, 'img': title_image_url}

        return interesting_entries, cache

    @staticmethod
    def send_mail(service, entries, log_file):
        """ Sends a text message to the defined recipient from the defined sender (gmail email) with the defined password

        Args:
            service: String city that these entries are coming from
            entries: Dictionary of the form{titleForAdd : {url: urlForAdd, img: imageForAdd}}
            log_file: File for writing logs to
        """
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(os.environ['SENDER'], os.environ['GMAIL_PASSWORD'])

        for key, info in entries.iteritems():
            msg = '{}:\n{} : {}\n {}'.format(service, key, info['url'], info['img'])

            message = MIMEText(msg)
            message['Date'] = formatdate()
            message['From'] = os.environ['SENDER']

            # Send notification to recepient
            server.sendmail(os.environ['SENDER'], os.environ['RECIPIENT'], message.as_string())

        log_file.write('{}: sent {} notifications \n'.format(service, len(entries.keys())))

        server.close()


    @staticmethod
    def get_log_file():
        """ Opens a file for the current date

        Returns:
            A file
        """
        now = datetime.datetime.now()
        file_name = 'logs/{}-{}-{}.txt'.format(now.month, now.day, now.year)
        mode = 'a' if os.path.exists(file_name) else 'w'

        return open(file_name, mode)

    def run(self):
        """ Grabs results form Denver/Boulder "free" listings every 1-3 minutes
        Sends results to the defined recipient in the environment variables
        """

        while True:

            log_file = self.get_log_file()
            for service in self.services:
                service_url = self.base_url.format(service)

                # Request
                log_file.write('Requesting from {}..'.format(service) + '\n')
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
                response = requests.get(service_url, headers=headers)

                # Parse
                beautiful_soup = BeautifulSoup(response.text)
                results_table = beautiful_soup.find_all('ul', class_='rows')

                if not results_table:
                    log_file.write('FAILED TO FIND THE TABLE FOR {}'.format(service))

                    # Cheat and leverage sendmail to notify recipient of failure to parse. Could mean we got a captcha
                    self.send_mail(service, {'N/A': {'url': 'Failed to find table for service', 'img': ''}}, log_file)
                    continue

                cache = self.caches[service]

                # Parse results, adding to the cache
                interesting_results, cache = self.parse_results(results_table[0], cache, log_file)

                # Send texts
                if interesting_results:
                    self.send_mail(service, interesting_results, log_file)


            sleep_time = randint(int(os.environ['SLEEP_MIN']), int(os.environ['SLEEP_MAX']))
            log_file.write('Sleeping for {} seconds'.format(sleep_time) + '\n')
            log_file.close()
            time.sleep(sleep_time)


# Run the service
watcher = CraigslistWatcher(None, None)
watcher.run()
