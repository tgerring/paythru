#!/usr/bin/python
from decimal import *
import yaml
import urlparse
import re
import datetime
import hashlib
import os
import json
import logging.config
import lib.db_mysql
import lib.email_smtp
import lib.dns_bitcoin
import lib.misc
import lib.paythrumail
import lib.http_bitcoin
import lib.bitcoin_spendfrom
import lib.twitter_rest
import lib.twilio_rest


class Paythru:
    def __init__(self, appconfigpath = 'app.yaml'):
        print 'Loading app config file from', appconfigpath
        self.appconfig = yaml.load(file(appconfigpath))['paythru']
        
        loggingconfigpath = self.appconfig['configfiles']['logging']
        loggerconfig = yaml.load(file(loggingconfigpath))
        logging.config.dictConfig(loggerconfig)
        self.logger = logging.getLogger(__name__)
        #self.logger.debug(str(loggerconfig))
        self.logger.info('Logging level: %s', logging.getLogger().getEffectiveLevel())

        self.validationconfig = lib.misc.getyamlconfig(self.appconfig['configfiles']['validation'])
        self.canonicalconfig = lib.misc.getyamlconfig(self.appconfig['configfiles']['canonicalmapping'])['canonicalmapping']

        self.transactionmaxageblocks = self.appconfig['transactionmaxageblocks']
        self.sitenamd = self.appconfig['sitename']
        self.hostname = self.appconfig['hostname']
        self.googleanalyticsid = self.appconfig['googleanalyticsid']
        self.forceredirect = self.appconfig['forceredirect']
        self.maxcanonicalsearchdepth = self.appconfig['maxcanonicalsearchdepth']
        self.notificationhourlimit = self.appconfig['notificationhourlimit']
        
        # TODO move this to app.yaml
        self.ignorelist = [
            'favicon.ico', 'http://favicon.ico',
            'robots.txt', 'http://robots.txt',
            'humans.txt', 'http://humans.txt'
        ]

        self.dataProvider = lib.db_mysql.mysql(
            self.appconfig['mysql']['server'],
            self.appconfig['mysql']['username'],
            self.appconfig['mysql']['password'],
            self.appconfig['mysql']['schema']
        )

        self.bitcoind2 = lib.bitcoin_spendfrom.BitcoinD(
            self.appconfig['bitcoind']['connectionstring'],
            self.appconfig['bitcoind']['walletpassword'],
            Decimal(self.appconfig['bitcoind']['networkfee']),
            self.appconfig['bitcoind']['simulatesend'],
            self.appconfig['bitcoind']['unlockseconds'],
            self.appconfig['bitcoind']['minconfs']
        )

        self.emailsmtp = lib.email_smtp.EmailSmtp(
            self.appconfig['emailsmtp']['server'],
            self.appconfig['emailsmtp']['username'],
            self.appconfig['emailsmtp']['password'],
            self.appconfig['emailsmtp']['port'],
            self.appconfig['emailsmtp']['usetls']
            )

        self.emailsconfig = lib.misc.getyamlconfig(self.appconfig['configfiles']['emails'])['emails']
        self.paythrumail = lib.paythrumail.PaythruMail(self.emailsconfig, hostname=self.hostname)
        self.DATAFILE = '../logs/BTCUSD.txt'



    def handleunclaimedfunds(self, maxageblocks = 4032):
        self.logger.info('Checking unspent transactions')

        balances = self.bitcoind2.list_available()
        #self.logger.debug('balances %s', balances)

        for address in balances:
            accountbalance = balances[address]
            self.logger.debug('Checking address %s with balance %f', address, accountbalance['total'])
            if ('account' not in accountbalance) or (not accountbalance['account']):
                self.logger.warn('Account name unkown. Skipping %s', accountbalance)
                continue

            if accountbalance['total'] <= self.appconfig['bitcoind']['networkfee']:
                self.logger.warn('Account %s balance of %s insufficient to pay fee %s. Skipping', accountbalance['account'], accountbalance['total'], self.appconfig['bitcoind']['networkfee'])
                continue



            self.logger.info('Looking for funds at generated addresses which have been claimed')
            for output in accountbalance["outputs"]:
                self.logger.debug('account: %s address: %s txid: %s', output['account'], output['address'], output['txid'])
                if not 'account' in output:
                    self.logger.warn('Unknown accounts on unspent transaction. Check %s', output)
                    continue

                po = self.getKnownAddress(output['account'])
                self.logger.debug('po.status: %s    po.address: %s', po.status, po.address)
                if address != po.address and (po.status == '2' or po.status == '3'):
                    self.logger.debug('About to send')
                    self.bitcoind2.spend_from(output["account"], po.address, output["amount"])
            self.logger.info('Done looking for funds to forward')



            self.logger.info('Attempting to refund unclaimed funds')
            self.bitcoind2.refund_from_withconfs(accountbalance["account"], maxageblocks)
            self.logger.info('Done trying to refund')


        self.logger.info('Done handling unclaimed funds')

    """
    def notifyuritransactions(self, blockdict):
        self.logger.info('Attempting to notify uris of any transactions')
        addressdict = self.dataProvider.getAddressUriDict()
        generatedaddressdict = self.dataProvider.getStaleGeneratedAddressUriDict()
        inputaddrs = []

        # do we have addresses to check and block txs to check against?
        if addressdict and len(addressdict) > 0 and blockdict and 'tx' in blockdict:
            self.logger.info('Checking block transactions')
            for tx in blockdict['tx']:

                #self.logger.debug('Building input address list')
                for inputtx in tx['inputs']:
                    #self.logger.debug(inputtx)
                    if 'prev_out' in inputtx:
                        inputaddrs.append(inputtx['prev_out']['addr'])
                #self.logger.debug(inputaddrs)

                #self.logger.debug('Checking outputs')
                for outputtx in tx['out']:
                    addr = outputtx['addr']
                    #self.logger.debug('Checking address %s', addr)

                    # is the output just a change address?
                    if addr in inputaddrs:
                        continue

                    if addr in addressdict:
                        self.logger.debug('Found match for address %s', addr)
                        notifyuri = addressdict[addr]
                        po = self.getKnownAddress(notifyuri)
                        notificationuri = self.tryNotify('transaction', po=po, outputtx=outputtx)
                        self.dataProvider.logNotification(po.uri, str(notificationuri))

                    if addr in generatedaddressdict:
                        self.logger.debug('Found match for old address %s', addr)
                        notifyuri = generatedaddressdict[addr]
                        po = self.getKnownAddress(notifyuri)
                        notificationuri = self.tryNotify('transactionstaleaddress', po=po, outputtx=outputtx)
                        self.dataProvider.logNotification(po.uri, str(notificationuri))
                        self.bitcoind2.spend_from(self.resolveduri, po.address)


        self.logger.info('Done looking')
    """

    def sanitizeInput(self, rawinput):
        # because re.sub returns the input string unmodified when no match occurs,
        # we prefix the sub pattern to detect "perfect" matching.
        matchprefix = '~'
        self.logger.info('Receieved raw input: %s', rawinput)
        # HACK until there is better routing at the api level
        if not rawinput or rawinput in self.ignorelist:
            self.logger.info('No rawinput, returning')
            return None
        result = None

        for item in self.validationconfig['regex']:
            matchexpr = '^' + item['match'].strip() + '$'
            subexpr = item['sub'].strip()
            self.logger.debug('Trying to match sanity pattern: %s', matchexpr)
            self.logger.debug('With sane substitution: %s', subexpr)

            subresult = re.sub(matchexpr, subexpr, rawinput, re.IGNORECASE)
            self.logger.debug('Result of sanity match/sub is: %s', subresult)
            # HACK see variable declaration
            if subresult.startswith(matchprefix):
                result = subresult[len(matchprefix):]
                self.logger.info('Found sane match resulting in %s', result)
                break
        if not result: self.logger.info('Could not sanitize input')
        return result

    def resolveCanonical(self, inputUri, depth = 0):
        self.logger.debug('Searching for canonical of %s with depth %s', inputUri, depth)
        if depth == self.maxcanonicalsearchdepth: return inputUri

        result = inputUri

        for item in self.canonicalconfig:
            matchexpr = '^' + item['match'].strip() + '$'
            subexpr = item['sub'].strip()
            self.logger.debug('Trying to match pattern: %s', matchexpr)
            self.logger.debug('With substitution: %s', subexpr)

            result = re.sub(matchexpr, subexpr, inputUri, re.IGNORECASE)
            self.logger.debug('Result of match/sub is: %s', result)
            if result != inputUri:
                result = self.resolveCanonical(result, depth + 1)
                break

        self.logger.debug('Canonical search depth %s complete', depth)

        if depth == 0:
            self.logger.info('Canonical search resulted in %s', result)

        return result

    def setUri(self, rawinput):
        if not rawinput:
            raise NotImplementedError('Invalid input')
        saneinput = self.sanitizeInput(rawinput)
        if not saneinput:
            raise NotImplementedError('Invalid input')
        self.resolveduri = self.resolveCanonical(saneinput)
        self.logger.debug('self.resolveduri = %s', self.resolveduri)

    def getUri(self, includeslashes = False):
        returnval = self.resolveduri
        self.logger.debug('getUri returnval %r', returnval)
        if includeslashes:
            # FIX magic literal
            if self.resolveduri.startswith('http:') and self.resolveduri[5:7] != '//':
                returnval = r'http://' + self.resolveduri[5:]

        self.logger.debug('getUri = %s', returnval)
        return returnval

    def getNewAddress(self):
        newaddress = self.bitcoind2.generate_new_address(self.getUri())
        self.logger.info('Generated address %s', newaddress)
        self.dataProvider.addNewAddress(self.resolveduri, newaddress)
        return self.getKnownAddress()

    def getKnownAddress(self, uri = None):
        if not uri and self.resolveduri:
            uri = self.resolveduri
        assert(uri)

        ID, knownaddress, knownuri, addressstatus, generatedaddress = self.dataProvider.getKnownAddress(uri)
        return lib.misc.UriAddressRecord(knownuri, knownaddress, addressstatus, generatedaddress, ID)

    def generateAuthcode(self):
        expiredelta = datetime.timedelta(hours=self.notificationhourlimit)
        self.logger.debug('expiredelta: %s', expiredelta)
        rightnow = datetime.datetime.utcnow()
        futuredate = rightnow + expiredelta
        salt = (futuredate).strftime('%Y-%m-%d %H:%M:%S')
        authcode = hashlib.sha224(self.resolveduri + salt).hexdigest()
        return (authcode, salt)


    def tryNotify(self, templatename=None, **kwargs):
        if not templatename: return []
        u = urlparse.urlparse(self.getUri(True))
        self.logger.info('Attempting to notify URI %s with template %s', u, templatename)
        contacts = None

        try:
            if u.scheme == 'http' or u.scheme == 'https':
                contacts = self.paythrumail.getWhoisContacts(u.netloc)
                # if not contacts:
                #     ba = lib.http_bitcoin.HttpBitcoinAddress('http://' + u.netloc)
                #     publishedaddress = ba.getMostFrequentEmail()
                #     contacts = [publishedaddress]
            elif u.scheme == 'mailto':
                contacts = [u.path]
            elif u.scheme == 'twitter':
                twitterconfig = self.appconfig['twitter']
                tr = lib.twitter_rest.TwitterRest(
                    twitterconfig['OAUTH_TOKEN'],
                    twitterconfig['OAUTH_SECRET'],
                    twitterconfig['CONSUMER_KEY'],
                    twitterconfig['CONSUMER_SECRET'])

                if templatename == 'newaddress':
                    themessage = '@%s Someone looked you up on http://%s/@%s Add a #Bitcoin address to your profile description to claim any despoits held' % (u.path, self.appconfig['hostname'], u.path)
                if templatename == 'newpublished':
                    themessage = '@%s Good news! Your #Bitcoin address on http://%s/@%s has been updated to match your profile description' % (u.path, self.appconfig['hostname'], u.path)

                statustext = tr.tryNotify(u.path, themessage)
            elif u.scheme == 'sms':
                twilioconfig = self.appconfig['twilio']
                t = lib.twilio_rest.TwilioRest(twilioconfig['account_sid'], twilioconfig['auth_token'])
                if templatename == 'newaddress':
                    themessage = 'Someone looked you up on http://%s/%s. Reply with your Bitcoin address to publish it' % (self.appconfig['hostname'], u.path)

                if themessage:
                    statustext = t.tryNotify(u.path, themessage)
            else:
                raise NotImplementedError('Protocol notification not supported')
                
        except Exception as e:
            self.logger.warn('Exception type: %s', type(e).__name__)
            # Assumption: This is non-fatal
            pass

        if contacts and len(contacts) > 0:
            self.logger.debug('templatename = %s', templatename)
            [subject, body] = self.paythrumail.rendertemplate(templatename, kwargs)
            emailfrom = self.appconfig['emailsmtp']['emailfrom']
            msgobj = self.paythrumail.composemessage(emailfrom, contacts, subject, body)
            self.emailsmtp.email(msgobj)

        return contacts

    def getPublishedAddress(self):
        publishedaddress = None
        u = urlparse.urlparse(self.getUri(True))
        self.logger.info('Attempting to resolve URI with scheme %s', u.scheme)
        
        if u.scheme == 'http' or u.scheme == 'https':
            try:
                dnsValidator = lib.dns_bitcoin.DnsBitcoin()
                dnsaddress = dnsValidator.getDns('bitcoin.' + u.netloc)
                publishedaddress = dnsaddress

                if not publishedaddress:
                    ba = lib.http_bitcoin.HttpBitcoinAddress('http://' + u.netloc)
                    publishedaddress = ba.getBitcoinMetatagAddress()

                if not publishedaddress:
                    publishedaddress = ba.getMostFrequentAddress()

            except Exception as e:
                self.logger.warn('Exception type: %s', type(e).__name__)
                # Assumption: This is non-fatal
                pass

        elif u.scheme == 'mailto':
            # no publishing mechanism for email currently
            pass
        elif u.scheme == 'twitter':
            twitterconfig = self.appconfig['twitter']
            tr = lib.twitter_rest.TwitterRest(
                twitterconfig['OAUTH_TOKEN'],
                twitterconfig['OAUTH_SECRET'],
                twitterconfig['CONSUMER_KEY'],
                twitterconfig['CONSUMER_SECRET'])
            publishedaddress = tr.getPublishedAddress(u.path)
        else:
            raise NotImplementedError('Protocol lookup not supported')

        self.logger.debug('publishedaddress = %s', publishedaddress)
        return publishedaddress

    def getCurrentBestAddress(self):
        po = self.getKnownAddress()
        self.logger.info('getCurrentBestAddress knownaddress = %s', po.address)

        if not po.address:
            publishedaddress = self.getPublishedAddress()
            self.logger.info('publishedaddress = %s', publishedaddress)
            if publishedaddress:
                # new entry with published address
                self.dataProvider.addNewAddress(self.resolveduri, publishedaddress, 2)
                po = self.getKnownAddress()
                notificationuri = self.tryNotify('newpublished', po = po)
                self.dataProvider.logNotification(po.uri, str(notificationuri))
            else:
                # completely new entry
                po = self.getNewAddress()
                [authcode, salt] = self.generateAuthcode()
                notificationuri = self.tryNotify('newaddress', po = po, authcode = authcode)
                self.dataProvider.logNotification(po.uri, str(notificationuri), authcode, salt)

        self.logger.info('bestaddress = %s with status %s', po.address, po.status)
        if not po.address:
            raise RuntimeError('Expected knownaddress to exist, but does not')

        return po

    def tryClaimFunds(self):
        bestaddress = None
        po = self.getKnownAddress()

        if po.status == 2:
            bestaddress = po.address
        else:
            publishedaddress = self.getPublishedAddress()
            self.logger.info('publishedaddress = %s', publishedaddress)
            if publishedaddress:
                bestaddress = publishedaddress
                self.dataProvider.updateAddress(self.resolveduri, publishedaddress)

        if bestaddress:
            self.bitcoind2.spend_from(self.resolveduri, bestaddress)


        authcode = None
        salt = None
        [authcode, salt] = self.generateAuthcode()
        notificationuri = self.tryNotify('claimconfirmation', po = po, authcode = authcode)
        self.dataProvider.logNotification(po.uri, str(notificationuri), authcode, salt)

        return True

    def updateNotification(self, authcode, newaddress):
        self.logger.info('Attempting to update notification for address %s', newaddress)
        #if not lib.bitcoin_address.validate(newaddress):
        if not self.bitcoind2.get_address_info(newaddress)["isvalid"]:
            raise RuntimeError('Address does not appear to be valid')
        self.dataProvider.updateAddress(self.resolveduri, newaddress)
        rowcount = self.dataProvider.updateNotification(self.resolveduri, authcode, newaddress)
        if rowcount:
            if rowcount == -1:
                raise RuntimeError('Invalid or expired authcode')
            elif rowcount in (0,1):
                # TODO this is not working as expected because we rely on getbalance, which is unreliable
                # instead, rely on getunspent by merging logic with refunds, old amt check, etc.
                self.bitcoind2.spend_from(self.resolveduri, newaddress)
                return True
            else:
                raise RuntimeError('dataProvider updated more rows than expected.')

    def logRequest(self, ipaddress, uri, method, result = None):
        self.dataProvider.logRequest(ipaddress, uri, method, result)

    def setprice(self, price):
        self.logger.debug('setprice price = %s', price)
        amt = float(price)

        filecontent = json.dumps({'updatetime': str(datetime.datetime.now()), 'BTCUSD': amt})
        with open(self.DATAFILE,'w') as f:
            f.write(filecontent)

    def getprice(self):
        with open(self.DATAFILE,'r') as f:
            jsondata = json.loads(f.read())

        return jsondata


if __name__ == "__main__":
    rawinput = r'https://www.taylorgerring.com/about/#footer?foo=bar'

    pt = Paythru()
    pt.setUri(rawinput)
    po = pt.getCurrentBestAddress()
    