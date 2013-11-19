import logging
import MySQLdb

class mysql:

    STATUSUPDATED = 2

    def __init__(self, hostname, username, password, schema):
        self.logger = logging.getLogger(__name__)
        self.HOSTNAME = hostname
        self.USERNAME = username
        self.PASSWORD = password
        self.SCHEMA = schema

        self.tryTesting()

    def tryTesting(self):
        
        conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)

        self.logger.info('Client: %s', MySQLdb.get_client_info())
        self.logger.info('Server: %s %s', conn.get_host_info(), conn.get_server_info())

        # TODO
        # self.logger.debug(str(result))
        # if result: return True
        # else: return False

        conn.close()


    def logRequest(self, ipaddress, uri, method, result = None):
        self.logger.info('Logging request: %s %s %s', ipaddress, method, uri)
        try:
            conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
            cur = conn.cursor()
            cur.execute("""INSERT INTO requests (requesttime, ipaddress, uri, method, result)
            VALUES (NOW(), %s, %s, %s, %s)""", (ipaddress, uri, method, result))
            conn.commit()
        except MySQLdb.Error, e:
            try:
                self.logger.exception('MySQL Error [%d]: %s', e.args[0], e.args[1])
            except IndexError:
                self.logger.error('MySQL Error: %s', str(e))
        resultcount = cur.rowcount
        conn.close()
        return cur.rowcount

    def getAddressUriDict(self):
        self.logger.info('Getting address/uri dictionary')
        addressdict = {}

        conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
        cur = conn.cursor()
        cur.execute("""SELECT address, uri FROM uri_addresses""")

        # NOTE there may be performnce implications here if the resultset grows large
        for row in cur.fetchall():
            addressdict[str(row[0])] = str(row[1])

        self.logger.info('Number of results: %d', len(addressdict))
        #self.logger.debug(addressdict)
        conn.close()
        return addressdict

    def getStaleGeneratedAddressUriDict(self):
        self.logger.info('Getting generated address/uri dictionary')
        generatedaddressdict = {}

        conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
        cur = conn.cursor()
        cur.execute("""SELECT generatedaddress, uri FROM uri_addresses WHERE generatedaddress != address""")

        # NOTE there may be performnce implications here if the resultset grows large
        for row in cur.fetchall():
            generatedaddressdict[str(row[0])] = str(row[1])

        self.logger.info('Number of results: %d', len(generatedaddressdict))
        #self.logger.debug(generatedaddressdict)
        conn.close()
        return generatedaddressdict

    def logNotification(self, uri, notificationuri, authcode = None, expiretime = None):
        self.logger.info('Logging notification')
        self.logger.debug('Expiring all previous notifications for uri %s', uri)
        conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
        cur = conn.cursor()
        cur.execute("""UPDATE notifications SET expiretime = NOW()
            WHERE uri = (%s)""", (uri))
        conn.commit()
        self.logger.debug('Adding a new notification for uri %s with expiretime %s', uri, expiretime)
        cur.execute("""INSERT INTO notifications (uri, notificationuri, authcode, expiretime)
            VALUES (%s, %s, %s, %s)""", (uri, notificationuri, authcode, expiretime))
        conn.commit()
        resultcount = cur.rowcount
        conn.close()
        return resultcount

    def updateNotification(self, uri, authcode, newaddress):
        self.logger.info('Updating notification for uri %s', uri)
        self.logger.info('%s %s %s', uri, authcode, newaddress)
        updatedrows = -1
        try:
            conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
            cur = conn.cursor()
            self.logger.info('Expiring notification with valid authcode')
            # NOTE careful with timezones
            cur.execute("""UPDATE notifications
                SET expiretime = NOW()
                WHERE uri = %s AND authcode = %s AND expiretime > NOW()
                """, (uri, authcode))
            conn.commit()
            updatedrows = cur.rowcount
            conn.close()
        except MySQLdb.Error, e:
            try:
                self.logger.exception('MySQL Error [%d]: %s', e.args[0], e.args[1])
            except IndexError:
                self.logger.error('MySQL Error: %s', str(e))

        self.logger.info('Updated %s rows', updatedrows)
        return updatedrows

    def getKnownAddress(self, inputUri):
        self.logger.info('Getting known address for %s', inputUri)
        ID = None
        address = None
        uri = None
        status = None
        addressgenerated = None
        conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
        cur = conn.cursor()
        cur.execute("""SELECT id, uri, address, status, generatedaddress FROM uri_addresses
            WHERE uri = %s ORDER BY status DESC""", (inputUri,))

        for row in cur.fetchall():
            ID = str(row[0])
            uri = str(row[1])
            address = str(row[2])
            status = str(row[3])
            addressgenerated = str(row[4])
            break #only take 1 result
        conn.close()
        return ID, address, uri, status, addressgenerated

    def addNewAddress(self, inputUri, newAddress, status = 1):
        self.logger.info('Adding new address to database')
        generatedaddress = newAddress
        if status == 2:
            generatedaddress = None

        conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
        cur = conn.cursor()
        cur.execute("""INSERT INTO uri_addresses (uri, address, generatedaddress, status)\
            VALUES (%s, %s, %s, %s)""", (inputUri, newAddress, generatedaddress, status))
        conn.commit()
        resultcount = cur.rowcount
        conn.close()
        return resultcount

    def updateAddress(self, inputUri, newAddress):
        self.logger.info('Updating address in database')
        conn = MySQLdb.connect(host = self.HOSTNAME, user = self.USERNAME, passwd = self.PASSWORD, db = self.SCHEMA)
        cur = conn.cursor()
        cur.execute("""UPDATE uri_addresses set address = %s, status = %s WHERE uri = %s""",
            (newAddress, self.STATUSUPDATED, inputUri))
        conn.commit()
        resultcount = cur.rowcount
        conn.close()
        return resultcount
