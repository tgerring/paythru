import socket
import bitcoinrpc.authproxy
from decimal import *
import logging

class BitcoinQt:

    def __init__(self, serviceuri, walletpassphrase = None, fee = Decimal('0.0001'), simulatesend = False):
        self.logger = logging.getLogger(__name__)
        self.FEE = round(fee, 8)
        self.WALLETPASSWORD = walletpassphrase
        self.SIMULATESEND = simulatesend

        try:
            self.logger.info('Creating bitcoind AuthServiceProxy')
            self.access = bitcoinrpc.authproxy.AuthServiceProxy(serviceuri)
        except:
            self.logger.error('Unable to connect to bitcoind')
            raise IOError('Unable to connect to bitcoind')

    def getRawTxDict(self, txid):
        self.logger.debug('getRawTxDict %s', txid)
        try:
            txdata = self.access.getrawtransaction(txid)
            transaction = self.access.decoderawtransaction(txdata)
        except bitcoinrpc.authproxy.JSONRPCException as e:
            self.logger.error(e)
            raise

        return transaction

    def getPrevTxOutputs(self, txid):
        self.logger.debug('getPrevTxOutputs %s', txid)

        txprevoutputs = []

        tx = self.getRawTxDict(txid)
        for txinput in tx['vin']:
            prevtx = self.getRawTxDict(txinput['txid'])
            inputaddress = prevtx['vout'][txinput['vout']]['scriptPubKey']['addresses'][0] #no multisig
            inputamount = prevtx['vout'][txinput['vout']]['value']
            txprevoutputs.append({'address': inputaddress, 'amount': inputamount})

        return txprevoutputs

    def listUnspent(self):
        self.logger.debug('listUnspent')
        return self.access.listunspent()

    def getTransaction(self, txid):
        return self.access.gettransaction(txid)

    def getAddressesWithBalance(self, minconfs = 1):
        return self.access.listreceivedbyaddress(minconfs, False)

    def fillkeypool(self):
            if self.WALLETPASSWORD:
                self.logger.debug('Unlocking wallet')
                self.access.walletpassphrase(self.WALLETPASSWORD, 30)
            self.logger.debug('keypoolrefill info: %s', self.access.keypoolrefill())
            if self.WALLETPASSWORD:
                self.logger.debug('Locking wallet')
                self.access.walletlock()

    def tryTesting(self):
        try:
            result = self.access.getinfo()
            self.logger.info(str(result))
            self.fillkeypool()
        except bitcoinrpc.authproxy.JSONRPCException as e:
            self.logger.warning('Is your wallet password correct? %s', str(e))
            raise
            return False
        except Exception, e:
            self.logger.error('%s %s', type(e), e.message)
            raise
            return False

        return True

    def generateNewAddress(self, inputUri):
        self.logger.info('generateNewAddress %s', inputUri)
        try:
            address = self.access.getnewaddress(inputUri)
            self.logger.info('Generated new address %s for URI %s', address, inputUri)
            # NOTE is this smart every time? need better logic for more efficiency?
            self.fillkeypool()
        except Exception, e:
            self.logger.error('Unable to connect to bitcoind: %s', str(e))
            raise IOError('Unable to connect to bitcoind')

        return address

    def getBalance(self, inputUri):
        self.logger.info('getbalance %s', inputUri)
        balances = self.getAccountBalances()

        if inputUri in balances:
            return balances[inputUri]
        else:
            return 0

    def getAccountBalances(self):
        self.logger.info('getAccountBalances')
        totals = {}

        balances = self.listUnspent()
        for accountbalance in balances:
            if 'account' in accountbalance and accountbalance['amount'] > 0:
                if not accountbalance['account'] in totals:
                    totals[accountbalance['account']] = 0
                totals[accountbalance['account']] += round(accountbalance['amount'], 8)

        return totals



        
    def sendfrom(self, inputUri, toAddress, amount = None):
        self.logger.info('sendfrom %s %s %s', inputUri, toAddress, amount)

        totalBalance = self.getBalance(inputUri)
        if totalBalance <= 0:
            return

        if not amount:
            amount = totalBalance

        amount = round(amount, 8)

        self.logger.debug('amount = %s', amount)

        if totalBalance < amount:
            self.logger.warn('totalBalance %s too little', totalBalance)
            return

        netAmount = round(amount - self.FEE, 8)
        self.logger.debug('netAmount = %s', netAmount)

        if self.WALLETPASSWORD:
            self.logger.debug('Unlocking wallet')
            self.access.walletpassphrase(self.WALLETPASSWORD, 30)

        self.logger.info('sendfrom %s to %s', inputUri, toAddress)
        if self.SIMULATESEND:
            self.logger.info('This will be a simulated send')
        if not self.SIMULATESEND:
            self.access.sendfrom(inputUri, toAddress, netAmount)

        if self.WALLETPASSWORD:
            self.logger.debug('Locking wallet')
            self.access.walletlock()
