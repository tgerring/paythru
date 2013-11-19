from urllib2 import Request, urlopen, URLError
from bs4 import BeautifulSoup
import logging
from collections import Counter
import bitcoin_address
import re

class HttpBitcoinAddress:
    def __init__(self, someurl = None):
        self.logger = logging.getLogger(__name__)
        self.thepage = None
        self.BITCOINREGEX = r'[13][1-9A-HJ-NP-Za-km-z]{20,40}'
        self.EMAILREGEX = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b'

        if someurl:
            self.makeRequest(someurl)

    def makeRequest(self, someurl):
        self.logger.debug('makeRequest to %s', someurl)
        req = Request(someurl)
        try:
            response = urlopen(req)
        except URLError as e:
            if hasattr(e, 'reason'):
                self.logger.error('Failed to reach the server: %s', e.reason);
            elif hasattr(e, 'code'):
                self.logger.error('The server couldn\'t fulfill the request: %s', e.code);
        else:
            self.logger.debug('Server response code: %s', response.getcode())
            self.thepage = response.read()
            #return self.thepage

    def getBitcoinMetatagAddress(self):
        theresult = None
        if not self.thepage:
            return theresult
        soup = BeautifulSoup(self.thepage)
        metatags = soup.head.find_all('meta', attrs={'name': "bitcoin"})
        self.logger.debug(metatags)
        for tag in metatags:
            # take the first result
            if 'content' in tag.attrs:
                theresult = tag['content']

        self.logger.info('Found meta tag address %s', theresult)
        return theresult

    def getMostFrequentAddress(self):
        theresult = None
        if not self.thepage:
            return theresult
        soup = BeautifulSoup(self.thepage)
        self.logger.debug('Testing against regex: %s', self.BITCOINREGEX)
        regexmatches = soup.find_all(text=re.compile(self.BITCOINREGEX))
        self.logger.info('Regex matches: %s', regexmatches)
        mostcommon = Counter(regexmatches).most_common()
        for addresstuple in mostcommon:
            address, count = addresstuple
            self.logger.debug('Checking address for vailidity: %s', address)
            if bitcoin_address.validate(address):
                theresult = address
                break
        self.logger.info('Best guess bitcoin address: %s', theresult)
        return theresult

