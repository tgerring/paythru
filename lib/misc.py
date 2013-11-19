import urllib
import yaml
import logging

logger = logging.getLogger(__name__)


def getyamlconfig(pathtoyaml):
    logger.info('Loading config file from %s', pathtoyaml)
    configobj = yaml.load(file(pathtoyaml))
    return configobj

def urlencode(inputurl):
    logger.debug('urlencode inputurl = %s', inputurl)
    return urllib.quote(inputurl).replace('/', '%2F')

def urldecode(inputurl):
    logger.debug('urldecode inputurl = %s', inputurl)
    return urllib.unquote(inputurl).replace('%2F', '/')

class UriAddressRecord:
    uri = None
    address = None
    status = None
    authcode = None
    generatedaddress = None

    def __init__(self, uri, address, status, generatedaddress, ID = None):
        self.uri = uri
        self.address = address
        self.status = status
        self.ID = ID
        self.generatedaddress = generatedaddress
        # FIX this should be an auto/translating attribute
        if (uri):
            self.resolveduri = urllib.quote(uri)