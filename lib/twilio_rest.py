import logging
import re
import httplib2
import bitcoin_address
import twilio
#from twilio.rest import TwilioRestClient

class TwilioRest:
    def __init__(self, account_sid, auth_token):
        self.logger = logging.getLogger(__name__)
        self.fromnumber = "+17086690248"
        self.BITCOINREGEX = r'[13][1-9A-HJ-NP-Za-km-z]{20,40}'
        self.client = TwilioRestClient(account_sid, auth_token)

    def getPublishedAddress(self, fromnumber, frommessage):

        self.logger.info('Checking messages from user %s', fromnumber)
        try:
            match = re.search(self.BITCOINREGEX, frommessage)
            if not match: return None
            self.logger.debug('Found %s', match.group(0))
            address = match.group(0)
            if bitcoin_address.validate(address):
                return address
        except twilio.TwilioRestException as e:
            self.logger.debug('TwilioRestException: %r', e)
        except Error as e:
            self.logger.error('Encountered an error: %r', e)

        return None

    def tryNotify(self, smsnumber, messagetext):
        self.logger.info('Notifying number user %s', smsnumber)
        try:
            message = self.client.sms.messages.create(body=messagetext, to=smsnumber, from_=self.fromnumber)
            print message.sid
        except twilio.TwilioRestException as e:
            self.logger.debug('TwilioRestException: %r', e)
            raise
        except Error as e:
            self.logger.error('Encountered an error: %r', e)
            raise

    def reply(self, messagetext):
        resp = twilio.twiml.Response()
        resp.message(messagetext)
        return str(resp)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    t = TwilioRest("", "")
    t.tryNotify("", "Someone looked you up on http://paythru.to/. Reply with your Bitcoin address to publish it")


