import sys, os, re, io
import email, mimetypes
from functools import reduce

invalid_chars_in_filename = '<>:"/\\|?*\%\'' + reduce(lambda x,y:x+chr(y), range(32), '')
invalid_windows_name='CON PRN AUX NUL COM1 COM2 COM3 COM4 COM5 COM6 COM7 COM8 COM9 LPT1 LPT2 LPT3 LPT4 LPT5 LPT6 LPT7 LPT8 LPT9'.split()

# email address REGEX matching the RFC 2822 spec from perlfaq9
#    my $atom       = qr{[a-zA-Z0-9_!#\$\%&'*+/=?\^`{}~|\-]+};
#    my $dot_atom   = qr{$atom(?:\.$atom)*};
#    my $quoted     = qr{"(?:\\[^\r\n]|[^\\"])*"};
#    my $local      = qr{(?:$dot_atom|$quoted)};
#    my $domain_lit = qr{\[(?:\\\S|[\x21-\x5a\x5e-\x7e])*\]};
#    my $domain     = qr{(?:$dot_atom|$domain_lit)};
#    my $addr_spec  = qr{$local\@$domain};
#
# Python's translation

atom_rfc2822=r"[a-zA-Z0-9_!#\$\%&'*+/=?\^`{}~|\-]+"
atom_posfix_restricted=r"[a-zA-Z0-9_#\$&'*+/=?\^`{}~|\-]+" # without '!' and '%'
atom=atom_rfc2822
dot_atom=atom  +  r"(?:\."  +  atom  +  ")*"
quoted=r'"(?:\\[^\r\n]|[^\\"])*"'
local="(?:"  +  dot_atom  +  "|"  +  quoted  +  ")"
domain_lit=r"\[(?:\\\S|[\x21-\x5a\x5e-\x7e])*\]"
domain="(?:"  +  dot_atom  +  "|"  +  domain_lit  +  ")"
addr_spec=local  +  "\@"  +  domain

email_address_re=re.compile('^'+addr_spec+'$')


class Attachment:
    def __init__(self, part, filename=None, type=None, payload=None, charset=None, content_id=None, description=None,
                 disposition=None, sanitized_filename=None, is_body=None):
        self.part = part  # original python part
        self.filename = filename  # filename in unicode (if any)
        self.type = type  # the mime-type
        self.payload = payload  # the MIME decoded content
        self.charset = charset  # the charset (if any)
        self.description = description  # if any
        self.disposition = disposition  # 'inline', 'attachment' or None
        self.sanitized_filename = sanitized_filename  # cleanup your filename here (TODO)
        self.is_body = is_body  # usually in (None, 'text/plain' or 'text/html')
        self.content_id = content_id  # if any
        if self.content_id:
            # strip '<>' to ease searche and replace in "root" content (TODO)
            if self.content_id.startswith('<') and self.content_id.endswith('>'):
                self.content_id = self.content_id[1:-1]


def getmailheader(header_text, default="ascii"):
    """Decode header_text if needed"""
    try:
        headers = email.header.decode_header(header_text)
    except email.errors.HeaderParseError:
        # This already append in email.base64mime.decode()
        # instead return a sanitized ascii string

        return header_text.encode('ascii', 'replace').decode('ascii')
    else:
        for i, (text, charset) in enumerate(headers):
            try:
                headers[i] = bytes(text, charset or default, errors='replace')
            except LookupError:
                # if the charset is unknown, force default
                headers[i] = bytes(text, default, errors='replace')
        return u"".join(str(headers))


def getmailaddresses(msg, name):
    """retrieve addresses from header, 'name' supposed to be from, to,  ..."""
    addrs = email.utils.getaddresses(msg.get_all(name, []))
    for i, (name, addr) in enumerate(addrs):
        if not name and addr:
            # only one string! Is it the address or is it the name ?
            # use the same for both and see later
            name = addr

        try:
            # address must be ascii only
            addr = addr.encode('ascii')
        except UnicodeError:
            addr = ''
        else:
            # address must match address regex
            if not email_address_re.match(str(addr)):
                addr = ''
        addrs[i] = (getmailheader(name), addr)
    return addrs


def search_message_bodies(mail):
    """search message content into a mail"""
    bodies = dict()
    _search_message_bodies(bodies, mail)
    return bodies


def get_mail_contents(msg,path):
    """split an email in a list of attachments"""

    attachments = []

    # retrieve messages of the email
    bodies = search_message_bodies(msg)
    # reverse bodies dict
    parts = dict((v, k) for k, v in bodies.items())

    # organize the stack to handle deep first search
    stack = [msg, ]
    while stack:
        part = stack.pop(0)
        type = part.get_content_type()
        if type.startswith('message/'):
            # ('message/delivery-status', 'message/rfc822', 'message/disposition-notification'):
            # I don't want to explore the tree deeper her and just save source using msg.as_string()
            # but I don't use msg.as_string() because I want to use mangle_from_=False
            from email.Generator import Generator
            fp = io.StringIO()
            g = Generator(fp, mangle_from_=False)
            g.flatten(part, unixfrom=False)
            payload = fp.getvalue()
            filename = 'mail.eml'
            attachments.append(
                Attachment(part, filename=filename, type=type, payload=payload, charset=part.get_param('charset'),
                           description=part.get('Content-Description')))
            URL_REGEX = r"""(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))"""
            f = open(str(path[0]) + "_maildetails.txt", "w")
            results = str(re.findall(URL_REGEX, str(payload)))
            results = results.replace(", ", "\n")
            results = results.replace("[", "")
            results = results.replace("]", "")
            results = results.replace("'", "")
            f.write("Links:" + "\n\n")
            f.write(results)
            f.close()
        elif part.is_multipart():
            # insert new parts at the beginning of the stack (deep first search)
            stack[:0] = part.get_payload()
            URL_REGEX = r"""(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))"""
            f = open(str(path[0]) + "_maildetails.txt", "w")
            results = str(re.findall(URL_REGEX, str(stack[:0] )))
            results = results.replace(", ", "\n")
            results = results.replace("[", "")
            results = results.replace("]", "")
            results = results.replace("'", "")
            f.write("Links:" + "\n\n")
            f.write(results)
            f.close()
        else:
            payload = part.get_payload(decode=True)
            URL_REGEX = r"""(?i)\b((?:https?:(?:/{1,3}|[a-z0-9%])|[a-z0-9.\-]+[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)/)(?:[^\s()<>{}\[\]]+|\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\))+(?:\([^\s()]*?\([^\s()]+\)[^\s()]*?\)|\([^\s]+?\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’])|(?:(?<!@)[a-z0-9]+(?:[.\-][a-z0-9]+)*[.](?:com|net|org|edu|gov|mil|aero|asia|biz|cat|coop|info|int|jobs|mobi|museum|name|post|pro|tel|travel|xxx|ac|ad|ae|af|ag|ai|al|am|an|ao|aq|ar|as|at|au|aw|ax|az|ba|bb|bd|be|bf|bg|bh|bi|bj|bm|bn|bo|br|bs|bt|bv|bw|by|bz|ca|cc|cd|cf|cg|ch|ci|ck|cl|cm|cn|co|cr|cs|cu|cv|cx|cy|cz|dd|de|dj|dk|dm|do|dz|ec|ee|eg|eh|er|es|et|eu|fi|fj|fk|fm|fo|fr|ga|gb|gd|ge|gf|gg|gh|gi|gl|gm|gn|gp|gq|gr|gs|gt|gu|gw|gy|hk|hm|hn|hr|ht|hu|id|ie|il|im|in|io|iq|ir|is|it|je|jm|jo|jp|ke|kg|kh|ki|km|kn|kp|kr|kw|ky|kz|la|lb|lc|li|lk|lr|ls|lt|lu|lv|ly|ma|mc|md|me|mg|mh|mk|ml|mm|mn|mo|mp|mq|mr|ms|mt|mu|mv|mw|mx|my|mz|na|nc|ne|nf|ng|ni|nl|no|np|nr|nu|nz|om|pa|pe|pf|pg|ph|pk|pl|pm|pn|pr|ps|pt|pw|py|qa|re|ro|rs|ru|rw|sa|sb|sc|sd|se|sg|sh|si|sj|Ja|sk|sl|sm|sn|so|sr|ss|st|su|sv|sx|sy|sz|tc|td|tf|tg|th|tj|tk|tl|tm|tn|to|tp|tr|tt|tv|tw|tz|ua|ug|uk|us|uy|uz|va|vc|ve|vg|vi|vn|vu|wf|ws|ye|yt|yu|za|zm|zw)\b/?(?!@)))"""
            f = open(str(path[0]) + "_maildetails.txt", "w")
            results= str(re.findall(URL_REGEX,str(payload)))
            results = results.replace(", ", "\n")
            results = results.replace("[", "")
            results = results.replace("]","")
            results = results.replace("'", "")
            f.write("Links:" + "\n\n")
            f.write(results)
            f.close()
            charset = part.get_param('charset')
            filename = get_filename(part)

            disposition = None
            if part.get_param('inline', None, 'content-disposition') == '':
                disposition = 'inline'
            elif part.get_param('attachment', None, 'content-disposition') == '':
                disposition = 'attachment'

            attachments.append(Attachment(part, filename=filename, type=type, payload=payload, charset=charset,
                                          content_id=part.get('Content-Id'),
                                          description=part.get('Content-Description'), disposition=disposition,
                                          is_body=parts.get(part)))

    return attachments


def get_filename(part):
    """Many mail user agents send attachments with the filename in
    the 'name' parameter of the 'content-type' header instead
    of in the 'filename' parameter of the 'content-disposition' header.
    """
    filename = part.get_param('filename', None, 'content-disposition')
    if not filename:
        filename = part.get_param('name', None)  # default is 'content-type'

    if filename:
        # RFC 2231 must be used to encode parameters inside MIME header
        filename = email.utils.collapse_rfc2231_value(filename).strip()

    if filename and isinstance(filename, str):
        # But a lot of MUA erroneously use RFC 2047 instead of RFC 2231
        # in fact anybody miss use RFC2047 here !!!
        filename = getmailheader(filename)

    return filename


def _search_message_bodies(bodies, part):
    """recursive search of the multiple version of the 'message' inside
    the the message structure of the email, used by search_message_bodies()"""

    type = part.get_content_type()
    if type.startswith('multipart/'):
        # explore only True 'multipart/*'
        # because 'messages/rfc822' are also python 'multipart'
        if type == 'multipart/related':
            # the first part or the one pointed by start
            start = part.get_param('start', None)
            related_type = part.get_param('type', None)
            for i, subpart in enumerate(part.get_payload()):
                if (not start and i == 0) or (start and start == subpart.get('Content-Id')):
                    _search_message_bodies(bodies, subpart)
                    return
        elif type == 'multipart/alternative':
            # all parts are candidates and latest is best
            for subpart in part.get_payload():
                _search_message_bodies(bodies, subpart)
        elif type in ('multipart/report', 'multipart/signed'):
            # only the first part is candidate
            try:
                subpart = part.get_payload()[0]
            except IndexError:
                return
            else:
                _search_message_bodies(bodies, subpart)
                return

        elif type == 'multipart/signed':
            # cannot handle this
            return

        else:
            # unknown types must be handled as 'multipart/mixed'
            # This is the peace of code could probably be improved, I use a heuristic :
            # - if not already found, use first valid non 'attachment' parts found
            for subpart in part.get_payload():
                tmp_bodies = dict()
                _search_message_bodies(tmp_bodies, subpart)
                for k, v in tmp_bodies.items():
                    if not subpart.get_param('attachment', None, 'content-disposition') == '':
                        # if not an attachment, initiate value if not already found
                        bodies.setdefault(k, v)
            return
    else:
        bodies[part.get_content_type().lower()] = part
        return

    return


def decode_text(payload, charset, default_charset):
    if charset:
        try:
            return payload.decode(charset), charset
        except UnicodeError:
            pass

    if default_charset and default_charset != 'auto':
        try:
            return payload.decode(default_charset), default_charset
        except UnicodeError:
            pass

    for chset in ['ascii', 'utf-8', 'utf-16', 'windows-1252', 'cp850']:
        try:
            return payload.decode(chset), chset
        except UnicodeError:
            pass

    return payload, None


if __name__ == "__main__":

    if len(sys.argv) > 1:
        raw = open(sys.argv[1]).read()

    loc=os.path.splitext(sys.argv[1])
    msg = email.message_from_string(raw)
    attachments = get_mail_contents(msg,loc)

    subject = getmailheader(msg.get('Subject', ''))
    from_ = getmailaddresses(msg, 'from')
    from_ = ('', '') if not from_ else from_[0]
    tos = getmailaddresses(msg, 'to')

    f = open(str(loc[0]) + "_maildetails.txt", "a")
    f.write('\n\n\n From: %r \n' % (from_,))
    f.write('\n To: %r \n' % (tos,))
    f.write('\n Subject: %r \n' % subject)
    f.close()


    for attach in attachments:
        # don't forget to be careful to sanitize 'filename' and be careful
        # for filename collision, to before to save :
        print ('\t filename=%r is_body=%s type=%s charset=%s desc=%s size=%d' % (
        attach.filename, attach.is_body, attach.type, attach.charset, attach.description,
        0 if attach.payload is None else len(attach.payload)))

        if attach.is_body == 'text/plain':
            # print first 3 lines
            payload, used_charset = decode_text(attach.payload, attach.charset, 'auto')
            for line in payload.split('\n')[:3]:
                # be careful console can be unable to display unicode characters
                if line:
                    print('\t\t', line)
