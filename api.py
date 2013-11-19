#!/usr/bin/env python
import sys, os
abspath = os.path.dirname(__file__)
sys.path.append(abspath)
os.chdir(abspath)
import logging
import json
import lib.misc
import web
import mimerender
import paythru
import yaml

routeconfigpath = 'config/routes.yaml'
routeconfig = yaml.load(file(routeconfigpath))
appconfigpath = routeconfig['appconfigpath']

URISEPARATOR = '/'

pt = paythru.Paythru(appconfigpath)
# pt.emailtemplateconfig = templateconfig['emails']
googleanalyticsid = pt.googleanalyticsid
logger = logging.getLogger(__name__)

templateconfig = routeconfig['templates']
render_json = lambda **args: json.dumps(args)
site_template = web.template.render(templateconfig['pages']['dirpath'], base=templateconfig['pages']['base'])
api_template = web.template.render(templateconfig['endpoints']['dirpath'])
html_template = web.template.render(templateconfig['endpoints']['dirpath'], base=templateconfig['endpoints']['base'])
mimerender = mimerender.WebPyMimeRender()

app = web.application(fvars=globals(), autoreload=False)
for item in routeconfig['routes']:
    app.add_mapping(item['route'], item['class'])
application = app.wsgifunc()

"""
def gettag(uristring, routedict):
    resolvedtag = None
    for tag in routedict.keys():
        if uristring.endswith(URISEPARATOR + tag):
            resolvedtag = routedict[tag]
            break

    return resolvedtag
"""

def scaffolding(rawuri):
    inputuri = rawuri
    """
    currency = gettag(rawuri, routeconfig['currencies'])
    if currency:
        inputuri = uristring[:-1 * len(URISEPARATOR + currency)]
    """
    try:
        pt.setUri(lib.misc.urldecode(inputuri))

        if pt.forceredirect and inputuri != pt.getUri():
            redirecturl = URISEPARATOR + lib.misc.urlencode(pt.getUri())
            #if currency: redirecturl += URISEPARATOR + currency

            logger.info('%s is not canonical. Redirecting to %s', inputuri, redirecturl)
            logRequest('301:' + redirecturl)
            raise web.redirect(redirecturl)

    except NotImplementedError, e:
        logRequest('404:' + str(e))
        raise web.notfound()
    except RuntimeError, e:
        logRequest('400:' + str(e))
        raise web.badrequest()
    except web.Redirect, e:
        logger.info(str(e))
        raise
    except Exception, e:
        logger.warn('Exception type: %s', type(e).__name__)
        raise

    logger.info('Scaffolding complete')
    return pt

def notfound():
    return web.notfound(site_template.notfound(pt.hostname, pt.appconfig['sitename'], googleanalyticsid))
app.notfound = notfound

def badrequest():
    return web.badrequest(site_template.badrequest(pt.hostname, pt.appconfig['sitename'], googleanalyticsid))
app.badrequest = badrequest

def logRequest(result = None):
    pt.logRequest(web.ctx['ip'], web.ctx['fullpath'], web.ctx['method'], result)

class index:
    def GET(self):
        logRequest()
        return site_template.index(pt.hostname, pt.appconfig['sitename'], googleanalyticsid)

class about:
    def GET(self):
        logRequest()
        return site_template.about(pt.hostname, pt.appconfig['sitename'], googleanalyticsid)

class developers:
    def GET(self):
        logRequest()
        return site_template.developers(pt.hostname, pt.appconfig['sitename'], googleanalyticsid)

class faq:
    def GET(self):
        logRequest()
        return site_template.faq(pt.hostname, pt.appconfig['sitename'], googleanalyticsid)


class smsmessage:
    @mimerender(
        default = 'json',
        json = render_json
    )   
    def POST(self):
        logger.info('Received %s to %s from %s. Attempting to update.', web.ctx['method'], web.ctx['fullpath'], web.ctx['ip'])
        postdata = web.input()

        try:
            pt.handlesms(postdata)
        except Exception as e:
            logger.error(e)
            raise badrequest()

        return {'status': 200}

    def GET(self):
        return 'Endpoint works :D'

class blocknotification:
    @mimerender(
        default = 'json',
        json = render_json
    )   
    def POST(self):
        logger.info('Received %s to %s from %s. Attempting to update.', web.ctx['method'], web.ctx['fullpath'], web.ctx['ip'])
        postdata = web.data()
        #logger.debug('postdata: %s', postdata)
        jsonbody = None
        
        try:
            if postdata:
                jsonbody = json.loads(postdata)
        except Exception as e:
            logger.error(e)
            raise badrequest()

        if jsonbody and 'USD' in jsonbody and '24h' in jsonbody['USD']:
            pt.setprice(jsonbody['USD']['24h'])

        """
        if jsonbody and 'tx' in jsonbody:
            pt.notifyuritransactions(jsonbody)"""

        if pt.transactionmaxageblocks >= 0:
            pt.handleunclaimedfunds(pt.transactionmaxageblocks)

        return {'status': 200}

    def GET(self):
        return 'Endpoint works :D'

class claim:
    def __init__(self):
        logger.info('claim called')
    @mimerender(
        default = 'html',
        html = html_template.claim
    )
    def GET(self, rawuri, authcode = None):
        if authcode and authcode.startswith('/'):
            authcode = authcode[len('/'):]

        scaffolding(rawuri)
        po = pt.getCurrentBestAddress()
        result = {
            'hostname': pt.hostname,
            'sitename': pt.appconfig['sitename'],
            'googleanalyticsid': googleanalyticsid,
            'address': po.address,
            'uri': po.uri,
            'addressstatus': po.status,
            'authcode': authcode
        }
        logRequest('200:' + str(result))
        return result

    @mimerender(
        default = 'html',
        html = html_template.claim
    )
    def POST(self, rawuri, authcode = None):
        resultmsg = 'Unable to complete your request'
        scaffolding(rawuri)
        i = web.input(newaddress = None)
        logger.info('POST input: %s', str(i))
        try:
            if i.newaddress and i.authcode:
                # NOTE this is a good entrypoint into a theorhetical pt.upsertNamecoinAlias()
                if pt.updateNotification(i.authcode, i.newaddress):
                    resultmsg = 'Updated Bitcoin address for this page.'
                else:
                    i.newaddress = ''
                    resultmsg = 'Could not update address on this page. Is your authcode correct? Get a new one by pressing the button at the bottom of this page.'
        except RuntimeError, e:
            resultmsg = 'Could not update Bitcoin address: ' + str(e)
            logger.info(resultmsg)

        po = pt.getCurrentBestAddress()
        result = {
            'hostname': pt.hostname,
            'sitename': pt.appconfig['sitename'],
            'googleanalyticsid': googleanalyticsid,
            'address': po.address,
            'uri': po.uri,
            'addressstatus': po.status,
            'resultmsg': resultmsg
        }
        logRequest('200:' + str(result))
        return result

class getaddress:
    def __init__(self):
        logger.info('getaddress called')
    @mimerender(
        default = 'html',
        json = api_template.jsonresponse,
        txt  = api_template.plaintext,
        html = html_template.getaddress,
        xml  = api_template.xmlresponse
    )
    def GET(self, rawuri):
        # this is strictly for debug
        if rawuri == 'localhost':
            return {
                'sitename': pt.appconfig['sitename'],
                'hostname': pt.appconfig['hostname'],
                'googleanalyticsid': pt.appconfig['googleanalyticsid'],
                'address': '1LoCALHoSTxxxxxxxxxxxxxxxxxxxxxxxx',
                'uri': 'localhost',
                'addressstatus': '1',
                'btcusd': 1
                }
        # try:
        scaffolding(rawuri)
        logger.info('pt.resolveduri = %s', pt.resolveduri)
        po = pt.getCurrentBestAddress()
        prices = pt.getprice()
        result = {
            'sitename': pt.appconfig['sitename'],
            'hostname': pt.appconfig['hostname'],
            'googleanalyticsid': googleanalyticsid,
            'address': po.address,
            'uri': po.uri,
            'addressstatus': po.status,
            'btcusd': prices['BTCUSD']
        }
        logRequest('200:' + str(result))
        return result
        # except Exception, e:
        #     logger.exception(str(e))
        #     raise web.internalerror()

    def POST(self, rawuri):
        pt = scaffolding(rawuri)
        claimresult = pt.tryClaimFunds()
        #po = pt.getCurrentBestAddress()

        redirecturl = '/' + lib.misc.urlencode(pt.getUri())
        logRequest('301:' + redirecturl)
        raise web.redirect(redirecturl)

if __name__ == "__main__":
    app.run()