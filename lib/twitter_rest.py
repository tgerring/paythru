import logging
import re
import httplib2
import bitcoin_address
from twitter import *


class TwitterRest:
    def __init__(self, OAUTH_TOKEN, OAUTH_SECRET, CONSUMER_KEY, CONSUMER_SECRET):
        self.logger = logging.getLogger(__name__)
        self.BITCOINREGEX = r'[13][1-9A-HJ-NP-Za-km-z]{20,40}'
        self.t = Twitter(
            auth=OAuth(OAUTH_TOKEN, OAUTH_SECRET, CONSUMER_KEY, CONSUMER_SECRET)
           )

    def getPublishedAddress(self, screen_name):
        self.logger.info('Getting published address for Twitter user %s', screen_name)
        try:
            userinfo = self.t.users.show(screen_name=screen_name)
            if 'description' not in userinfo: return None
            match = re.search(self.BITCOINREGEX, userinfo['description'])
            if not match: return None
            self.logger.debug('Found %s', match.group(0))
            address = match.group(0)
            if bitcoin_address.validate(address):
                return address
        except TwitterHTTPError as e:
            self.logger.debug('TwitterHTTPError: %r', e.response_data)
        except Error as e:
            self.logger.error('Encountered an error: %r', e)

        return None

    def tryNotify(self, screen_name, messagetext):
        self.logger.info('Notifying Twitter user %s', screen_name)
        try:
            self.t.statuses.update(status=messagetext)
        except TwitterHTTPError as e:
            self.logger.debug('TwitterHTTPError: %r', e.response_data)
            raise
        except Error as e:
            self.logger.error('Encountered an error: %r', e)
            raise

