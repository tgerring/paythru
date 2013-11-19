from HTMLParser import HTMLParser
import web
import whois
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import lib.misc

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_tags(html):
        s = MLStripper()
        s.feed(html)
        return s.get_data()

class PaythruMail:
    def __init__(self, emailsconfig, hostname='localhost'):
        self.logger = logging.getLogger(__name__)
        self.config = emailsconfig
        self.hostname = hostname

    def rendertemplate(self, configkey, *args):
        emailconfig = self.config[configkey]
        self.logger.info('Loading email configuration %s', str(emailconfig))
        subject = emailconfig['subject']
        bodyfile = emailconfig['bodyfile']
        render = web.template.frender(bodyfile)
        messagehtml = render(self.hostname, *args)
        self.logger.debug(messagehtml)
        return (subject, str(messagehtml))

    def composemessage(self, emailfrom, emailto, subject, messagehtml):
        EMAILSEPARATOR = ','
        self.logger.info('Composing email message for <%s> with subject `%s`', emailto, subject)
        messagetext = strip_tags(messagehtml)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = emailfrom
        if type(emailto) == list:
            msg['To'] = EMAILSEPARATOR.join(emailto)
        else: # assume str
            msg['To'] = emailto
        msg.attach(MIMEText(messagetext, 'plain'))
        msg.attach(MIMEText(messagehtml, 'html'))
        self.logger.debug('Composition complete')
        return msg

    def getWhoisContacts(self, domain):
        self.logger.info('Looking up WHOIS for %s', domain)
        # FIX how to resolve third+ level domains?
        try:
            w = whois.whois(domain)
        # HACK because of a bug in whois.whois
        except UnboundLocalError:
            return []
        except whois.parser.PywhoisError as e:
            self.logger.warn('Could not look up WHOIS: %s', str(e))
            return []

        emails_unique = list(set(w.emails))
        self.logger.info('Found WHOIS emails %s', str(emails_unique))
        return emails_unique
