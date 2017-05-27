def poll(timeout=0.0, map=None):
    pass

def loop(timeout=30.0, use_poll=False, map=None, count=None):
    pass

def main():
    '''
    Entry point. Gather all files in one list and start create_docs function.
    '''
    pass

def fill_html(htmlfile, astrees, files, args):
    '''
    Fill html file with code.
    This function gathers all docstrings into one dictionary and sends it into jinja2
    Template render. Then rendered html-code goes to htmlfile.
    '''
    pass