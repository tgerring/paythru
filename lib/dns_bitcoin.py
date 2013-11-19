import bitcoin_address
import dns.resolver
import logging

class NetworkError(IOError):
    pass

class DnsBitcoin:
    def __init__(self):
        self.QUOTESTRING = '"'
        self.logger = logging.getLogger(__name__)

    def getDns(self, domain_name):
        self.logger.info('Getting DNS TXT for %s', domain_name)
        result = None
        try:
            answers = dns.resolver.query(domain_name, 'TXT')
        except Exception as e:
            msg = 'Unable to read DNS entries for domain ' + domain_name + ': ' + str(e)
            self.logger.warning(msg)
            #raise NetworkError(msg)
        else:
            for rdata in answers:
                data = rdata.to_text()
                if data.startswith(self.QUOTESTRING) and data.endswith(self.QUOTESTRING):
                    data = data[len(self.QUOTESTRING):-1 * len(self.QUOTESTRING)]
                self.logger.info('Found %s', data)

                if bitcoin_address.validate(data):
                    result = data
                    break
        
        self.logger.info('Found %s', result)
        return result
