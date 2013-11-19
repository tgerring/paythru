# adapted form Gaving Andresen's contrib/spendfrom

from decimal import *
import time
import logging
import json
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

def check_json_precision():
    """Make sure json library being used does not lose precision converting BTC values"""
    n = Decimal("20000000.00000003")
    satoshis = int(json.loads(json.dumps(float(n)))*1.0e8)
    if satoshis != 2000000000000003:
        raise RuntimeError("JSON encode/decode loses precision")

class TransactionError(RuntimeError):
    pass

class FeeError(RuntimeError):
    pass

class BitcoinD:
    def __init__(self, connecturi, passphrase, fee = Decimal("0.0001"), simulatespend = False, unlockseconds = 5, minconfs = 1):
        check_json_precision()

        self.logger = logging.getLogger(__name__)
        self.SIMULATEONLY = simulatespend
        self.BASE_FEE = fee
        self.MINCONFS = minconfs
        self.UNLOCKSECONDS = unlockseconds

        self.bitcoind = self.connect_JSON(connecturi, passphrase)


    def connect_JSON(self, connect, passphrase):
        """Connect to a bitcoin JSON-RPC server"""
        try:
            result = AuthServiceProxy(connect)
            # ServiceProxy is lazy-connect, so send an RPC command mostly to catch connection errors,
            # but also make sure the bitcoind we're talking to is/isn't testnet:
            if result.getmininginfo()['testnet']:
                self.logger.info("Connected to testnet")
            else:
                self.logger.info("Connected to mainnet")
            result.passphrase = passphrase

            return result
        except:
            raise

    def unlock_wallet(self):
        self.logger.debug("Unlocking wallet")
        info = self.bitcoind.getinfo()
        if 'unlocked_until' not in info:
            return True # wallet is not encrypted
        # NOTE This assumes clocks are sync'd. True on localhost
        t = int(info['unlocked_until'])
        if t <= time.time():
            try:
                self.bitcoind.walletpassphrase(self.bitcoind.passphrase, self.UNLOCKSECONDS)
            except:
                raise RuntimeError("Could not unlock wallet. Incorrect passphrase?")

        info = self.bitcoind.getinfo()
        return int(info['unlocked_until']) > time.time()

    def list_addresses(self, searchaccount = None):
        self.logger.debug("list_addresses called with searchaccount = %s", searchaccount)
        address_to_account = dict()
        for info in self.bitcoind.listreceivedbyaddress(self.MINCONFS):
            if not searchaccount or searchaccount == info["account"]:
                address_to_account[info["address"]] = info["account"]

        self.logger.debug("list_addresses returns object of length %d", len(address_to_account))
        return address_to_account


    def list_available(self, searchaccount = None):
        self.logger.debug("list_available called with searchaccount = %s", searchaccount)
        address_summary = dict()
        address_to_account = self.list_addresses(searchaccount)
        unspent = self.bitcoind.listunspent(self.MINCONFS)

        for output in unspent:
            self.logger.debug("Checking output of txid %s", output["txid"])
            # listunspent doesn't give addresses, so:
            rawtx = self.bitcoind.getrawtransaction(output['txid'], 1)
            vout = rawtx["vout"][output['vout']]
            pk = vout["scriptPubKey"]

            # This code only deals with ordinary pay-to-bitcoin-address
            # or pay-to-script-hash outputs right now; anything exotic is ignored.
            if pk["type"] != "pubkeyhash" and pk["type"] != "scripthash":
                self.logger.warning("Unsupported transaction type")
                continue
            
            address = pk["addresses"][0]

            #self.logger.debug("searchaccount = %s; address = %s", searchaccount, address)
            if not searchaccount or address in address_to_account:

                if not address in address_summary:
                    address_summary[address] = {
                        "account" : address_to_account.get(address, ""),
                        "total" : vout["value"],
                        "outputs" : [output]
                        }
                else:
                    address_summary[address]["total"] += vout["value"]
                    address_summary[address]["outputs"].append(output)

        self.logger.debug("list_available returns an object of length %d", len(address_summary))
        return address_summary

    def select_coins(self, needed, inputs):
        # Feel free to improve this, this is good enough for my simple needs:
        outputs = []
        have = Decimal("0.0")
        n = 0
        while have < needed and n < len(inputs):
            outputs.append({ "txid":inputs[n]["txid"], "vout":inputs[n]["vout"]})
            have += inputs[n]["amount"]
            n += 1
        return (outputs, have-needed)

    def create_tx(self, fromaddresses, toaddress, amount, fee):
        self.logger.info("create_tx fromaddresses=%s; toaddress=%s; amount=%f, fee=%f"%(fromaddresses, toaddress, amount, fee))
        if amount < 0:
            raise TransactionError("Transaction amount is negative")
        all_coins = self.list_available()

        total_available = Decimal("0.0")
        needed = Decimal(amount)+fee
        potential_inputs = []
        for addr in fromaddresses:
            if addr not in all_coins:
                continue
            potential_inputs.extend(all_coins[addr]["outputs"])
            total_available += all_coins[addr]["total"]

        if total_available < needed:
            raise TransactionError("Error, only %f BTC available, need %f"%(total_available, needed))

        #
        # Note:
        # Python's json/jsonrpc modules have inconsistent support for Decimal numbers.
        # Instead of wrestling with getting json.dumps() (used by jsonrpc) to encode
        # Decimals, I'm casting amounts to float before sending them to bitcoind.
        #  
        outputs = { toaddress : float(amount) }
        (inputs, change_amount) = self.select_coins(needed, potential_inputs)
        if change_amount > self.BASE_FEE:  # don't bother with zero or tiny change
            change_address = fromaddresses[-1]
            if change_address in outputs:
                outputs[change_address] += float(change_amount)
            else:
                outputs[change_address] = float(change_amount)

        self.logger.debug('inputs: %s\noutputs: %s'%(inputs,outputs))

        rawtx = self.bitcoind.createrawtransaction(inputs, outputs)
        signed_rawtx = self.bitcoind.signrawtransaction(rawtx)
        if not signed_rawtx["complete"]:
            raise RuntimeError("signrawtransaction failed")
        txdata = signed_rawtx["hex"]

        return txdata

    def compute_amount_in(self, txinfo):
        result = Decimal("0.0")
        for vin in txinfo['vin']:
            in_info = self.bitcoind.getrawtransaction(vin['txid'], 1)
            vout = in_info['vout'][vin['vout']]
            result = result + vout['value']
        return result

    def compute_amount_out(self, txinfo):
        result = Decimal("0.0")
        for vout in txinfo['vout']:
            result = result + vout['value']
        return result

    def sanity_test_fee(self, txdata_hex, fee, max_fee):
        txinfo = self.bitcoind.decoderawtransaction(txdata_hex)
        total_in = self.compute_amount_in(txinfo)
        total_out = self.compute_amount_out(txinfo)
        if total_in-total_out > max_fee:
            raise FeeError("Rejecting transaction, unreasonable fee of "+str(total_in-total_out))

        tx_size = len(txdata_hex)/2
        kb = tx_size/1000  # integer division rounds down
        if kb > 1 and fee < self.BASE_FEE:
            raise FeeError("Rejecting no-fee transaction, larger than 1000 bytes")
        if total_in < 0.01 and fee < self.BASE_FEE:
            raise FeeError("Rejecting no-fee, tiny-amount transaction")
        # Exercise for the reader: compute transaction priority, and
        # warn if this is a very-low-priority transaction


    def refill_keypool(self):
        self.unlock_wallet()
        self.bitcoind.keypoolrefill()

    def generate_new_address(self, acctname):
        address = self.bitcoind.getnewaddress(acctname)
        self.refill_keypool()
        return address

    def make_spendfrom_args(self, acctname = None):
        self.logger.debug("make_spendfrom_args acctname =%s"%acctname)
        acctamount = Decimal(0)
        fromaddresses = ""

        address_summary = self.list_available()
        for address,info in address_summary.iteritems():
            #self.logger.debug("info.account = %s"%info['account'])
            if not acctname or acctname == info['account']:
                acctamount += info['total']
                fromaddresses += ("," + address)
                #self.logger.debug("%f %s"%(acctamount, fromaddresses))


        addresslist = fromaddresses[1:]
        self.logger.debug("acctamt = %s; fromaddresses = %s", acctamount, addresslist)
        return acctamount, addresslist

    def spend_from(self, acctname, toaddress, amount = None):
        fee = Decimal(self.BASE_FEE)

        try:
            accounttotal, fromaddresses = self.make_spendfrom_args(acctname)

            if not amount:
                amount = accounttotal

            self.logger.debug("spend_from acctname = %s, toaddress = %s, amount = %f", acctname, toaddress, amount)

            netamount = Decimal(amount) - Decimal(fee)
            if not netamount or netamount <= 0: # sanity check
                self.logger.warning('Non-positive netamount, exiting')
                return
            if toaddress in fromaddresses:
                self.logger.warning('Desired output address includes input address')
                return

            self.logger.info('Planning to send %f to %s with fee of %f', netamount, toaddress, fee)
            self.unlock_wallet()
            txdata = self.create_tx(fromaddresses.split(","), toaddress, netamount, fee)
            #self.sanity_test_fee(txdata, fee, Decimal(amount)*Decimal("0.01"))
            self.logger.debug('Preparing to send transaction data\n%s'%txdata)
            if self.SIMULATEONLY:
                self.logger.info("The resulting transaction is ***SIMULATEONLY***")
            else:
                txid = self.bitcoind.sendrawtransaction(txdata)
                self.logger.info("The resulting transaction is %s", txid)
        except JSONRPCException as e:
            raise TransactionError(e.error)
        except FeeError as e:
            raise
        except TransactionError as e:
            raise
        except Exception as e:
            raise
        self.logger.info("Transaction broadcast successfully")


    def get_txid_inputs(self, txid):
        self.logger.debug("get_txid_inputs txid = %s", txid)
        txinfo = self.bitcoind.getrawtransaction(txid, 1)
        result = []
        for vin in txinfo['vin']:
            in_info = self.bitcoind.getrawtransaction(vin['txid'], 1)
            vout = in_info['vout'][vin['vout']]
            result.append(vout)
        self.logger.debug("get_txid_inputs returning %s", result)
        return result

    def refund_from_withconfs(self, accountname = None, maxconfirmations = 2016):
        self.logger.debug("refund_from_withconfs called with accountname = %s and maxconfirmations = %s", accountname, maxconfirmations)
        refundaddresses = self.list_available(accountname)
        address_to_account = self.list_addresses()
        for address in refundaddresses:
            info = refundaddresses[address]
            for output in info["outputs"]:
                if output["confirmations"] > maxconfirmations:
                    self.logger.info("Getting inputs of %s", output["txid"])
                    tx = self.get_txid_inputs(output["txid"])
                    for n in tx:
                        self.spend_from(output["account"], n["scriptPubKey"]["addresses"][0], output["amount"])

    def get_address_info(self, address):
        return self.bitcoind.validateaddress(address)

    def sign_message(self, address, message):
        self.logger.debug("Signing message with address %s", address)
        try:
            self.unlock_wallet()
            return self.bitcoind.signmessage(address, message)
        except JSONRPCException as e:
            raise RuntimeError(e.error)

    def verify_signature(self, address, signature, message):
        self.logger.debug("Verifying message with address %s", address)
        try:
            return self.bitcoind.verifymessage(address, signature, message)
        except JSONRPCException as e:
            raise RuntimeError(e.error)




