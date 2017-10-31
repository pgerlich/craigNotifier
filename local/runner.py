import requests
from bs4 import BeautifulSoup


def parse_patents(table):
    parsed_items = []

    for tr in table.find_all('tr')[1:]:
        entry = {}
        for index, td in enumerate(tr.find_all('td')):
            if index == 0:  # Rank
                entry['patent.rank'] = td.contents[1].string.strip()
            elif index == 1:  # Document #
                entry['patent.number'] = td.contents[0].strip()
            elif index == 2:  # Title / Summary
                title = td.contents[1].string.strip()
                summary = td.contents[4].string.strip()
                entry['patent.meta'] = {
                    'title': title,
                    'summary': summary,
                    'url': td.find_all('a')[0]['href']
                }
            elif index == 3:  # Score
                entry['patent.score'] = td.contents[0].string.strip()

        parsed_items.append(entry)
    return parsed_items


def lambda_handler(event, context):
    """
    Given the query and page number, parses freepatentsonline.com and grabs all 50 results from the table using
    beautiful soup and lxml
    
    :param event: 
    :param context: 
    :return: 
    """
    # Grab payload/filters
    payload = event.get('payload')
    page = payload.get('page', 0)

    # Grab filters/query
    query = payload.get('query')
    base_url = 'http://www.freepatentsonline.com/' \
               'result.html?sort=relevance&srch=top&query_txt={0}&patents=on&p={1}'.format(query, page)

    print 'Downloading from url %s' % base_url

    response = requests.get(base_url)

    print 'Retrieved Response (status: {}), Parsing with lxml'.format(response.status_code)

    beautiful_soup = BeautifulSoup(response.text, "lxml")
    results_table = beautiful_soup.find_all('table', class_='listing_table')[0]

    print 'Grabbed table, parsing for patents'

    results = parse_patents(results_table)

    print 'Parsed {} results'.format(len(results))

    return results

lambda_handler({'payload': {'page': 0, 'query': 'computer'}}, None)

