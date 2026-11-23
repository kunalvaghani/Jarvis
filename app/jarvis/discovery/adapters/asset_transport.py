"""Public HTTPS bytes only: pinned DNS address, TLS hostname verification, bounds.

No proxy credentials, cookie jar, scripts, archive extraction or auto retry.
The provider adapter must supply its independently qualified redirect hosts.
"""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin,urlsplit


class TransferError(ValueError):pass


def public_address(value):
    ip=ipaddress.ip_address(value)
    # RFC 6052's well-known NAT64 /96 may be marked reserved by Python even
    # when it embeds a public IPv4 destination. Validate the embedded address;
    # this must never admit NAT64 representations of private/loopback targets.
    if isinstance(ip,ipaddress.IPv6Address) and ip in ipaddress.IPv6Network('64:ff9b::/96'):
        ip=ipaddress.IPv4Address(int(ip)&0xffffffff)
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def address(url,hosts,resolver=socket.getaddrinfo):
    try:
        p=urlsplit(url)
        if (p.scheme!='https' or p.hostname not in hosts or p.port not in (None,443)
                or p.username or p.password or p.fragment or len(url)>8000
                or any(ord(c)<32 for c in url)):
            raise TransferError('download URL is outside the admitted HTTPS hosts')
        rows=resolver(p.hostname,443,type=socket.SOCK_STREAM)
        ips=list(dict.fromkeys(str(row[4][0]) for row in rows))
        if not ips or any(not public_address(ip) for ip in ips):
            raise TransferError('download DNS did not resolve exclusively to public addresses')
        # Prefer a public IPv4 answer where present; retain IPv6-only support.
        ips.sort(key=lambda ip:ipaddress.ip_address(ip).version)
        return p,ips[0]
    except (ValueError,OSError) as exc:
        if isinstance(exc,TransferError):raise
        raise TransferError('download URL or public DNS validation failed') from None


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip,timeout):
        super().__init__(host,443,timeout=timeout,context=ssl.create_default_context())
        self.ip=ip

    def connect(self):
        # Connect to the validated literal IP, never resolve the host again.
        plain=socket.create_connection((self.ip,443),timeout=self.timeout)
        try:self.sock=self._context.wrap_socket(plain,server_hostname=self.host)
        except BaseException:
            plain.close();raise


def stream(url,hosts,maximum_bytes,sink,*,cancelled=lambda:False,seconds=40,
           resolver=socket.getaddrinfo,connection=PinnedHTTPS):
    if type(maximum_bytes) is not int or not 4<=maximum_bytes<=20_000_000:
        raise TransferError('bounded asset byte allowance required')
    if type(seconds) not in (int,float) or not 1<=seconds<=40:raise TransferError('bounded transfer deadline required')
    if not hosts or len(hosts)>8:raise TransferError('bounded provider host policy required')
    deadline=time.monotonic()+seconds;total=0
    for redirect in range(4):
        if cancelled():raise TransferError('download cancelled before request')
        parsed,ip=address(url,hosts,resolver)
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TransferError('download deadline reached')
        conn=connection(parsed.hostname,ip,min(10,remaining))
        try:
            path=parsed.path or '/'
            if parsed.query:path+='?'+parsed.query
            conn.request('GET',path,headers={'User-Agent':'Jarvis-inert-asset-acquisition/1.0','Accept-Encoding':'identity'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                target=response.getheader('Location')
                if not target or redirect==3:raise TransferError('download redirect allowance exhausted')
                url=urljoin(url,target);continue
            if response.status!=200:raise TransferError('download HTTP status '+str(response.status))
            if response.getheader('Content-Encoding','identity').lower() not in ('identity',''):
                raise TransferError('HTTP content encoding is not an admitted inert file')
            length=response.getheader('Content-Length')
            if length is not None and (not length.isdecimal() or int(length)>maximum_bytes):
                raise TransferError('declared download size exceeds admission')
            while True:
                if cancelled() or time.monotonic()>=deadline:raise TransferError('download cancelled or deadline reached')
                chunk=response.read(min(65536,maximum_bytes-total+1))
                if not chunk:break
                total+=len(chunk)
                if total>maximum_bytes:raise TransferError('download exceeded admitted byte limit')
                sink.write(chunk)
            if total<4 or (length is not None and total!=int(length)):
                raise TransferError('download is empty or incomplete')
            # Signed query strings are deliberately absent from returned evidence.
            return {'bytes':total,'final_host':parsed.hostname,'redirects':redirect,
                'etag':str(response.getheader('ETag',''))[:200]}
        except (OSError,http.client.HTTPException,ssl.SSLError):
            raise TransferError('download transport failed; partial data must be reconciled') from None
        finally:conn.close()
    raise TransferError('download did not complete')
