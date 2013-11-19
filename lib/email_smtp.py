
import smtplib
import logging



class EmailSmtp:

    def __init__(self, server, user, passwd, port = 587, tls = True):
        self.logger = logging.getLogger(__name__)
        self.SMTPSERVER = server
        self.SMTPUSER = user
        self.SMTPPASSWD = passwd
        self.SMTPPORT = port
        self.SMTPTLS = tls


    def email(self, msgobj):
        prefix = 'mailto:'
        self.logger.info('Sending email to %s with subject %s', msgobj['To'], msgobj['Subject'])

        try:
            server = smtplib.SMTP(
                host = self.SMTPSERVER,
                port = self.SMTPPORT,
                timeout = 15
            )
            if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
                server.set_debuglevel(10)
            if self.SMTPTLS == True:
                server.starttls()
            server.ehlo()
            server.login(self.SMTPUSER, self.SMTPPASSWD)
            server.sendmail(msgobj['From'], msgobj['To'], msgobj.as_string())
            self.logger.debug(server.quit())
            return True
        except AttributeError, e:
            raise e
        except Exception, e:
            self.logger.exception('Couldn\'t send mail: %s', str(e))
            return False
