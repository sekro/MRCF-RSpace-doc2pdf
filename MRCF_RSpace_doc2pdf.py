"""
MRCF / ISB / NTNU RSpace Documents to pretty PDFs Script
Sebastian Krossa 09/2026
NTNU Trondheim
sebastian.krossa@ntnu.no
"""

import argparse
import os
import json
import sys
from collections import namedtuple
import rspace_client
from bs4 import BeautifulSoup
import re
from pathvalidate import sanitize_filename
from weasyprint import HTML, CSS

g_defaults = {
    'template': 'full',
    'title': None,
    'rspace_cfg': 'rspace.json',
    'sop_approver': ''
}

g_report_templates = {
    'full': 'report_full_template',
    'mrcf_full': 'MRCF-report_full_template',
    'mrcf_simple': 'MRCF-simple',
    'mrcf_sop': 'MRCF-SOP'
}

g_report_template_file_names = {
    "report_html": "main.html",
    "report_css": "main.css",
    "report_eln_html": "eln_page.html",
    "report_toc_html": "toc.html",
}

g_expected_template_files = [
    "report_html",
    "report_css",
    "report_eln_html"
]

g_eln_doc_specs = {
    'globalId': '$DOCID$',
    'name': '$DOCNAME$',
    'owner': '$AUTHOR$',
    'version': '$DOCVERSION$'
}

# This is expecting the default MRCF experiment form
g_eln_extract = {
    'Date': '$DATE$',
    'Title': '$TITLE$',
    'Purpose': '$PURPOSE$',
    'Materials and Methods': '$MATSMETHODS$',
    'Procedure': '$PROCEDURE$',
    'Results': '$RESULTS$',
    'Conclusion': '$CONCLUSION$'
}

Eln_data = namedtuple("Eln_data", ["id", "html", "data", "extract"])

def get_extract(fp):
    if os.path.isfile(fp):
        with open(fp, 'r') as f:
            return json.load(f)

def extract_data_from_eln(eln_doc, extract=None, extract_page=None):
    if extract is None:
        extract = g_eln_extract
    else:
        extract = get_extract(extract)
    if (not extract_page is None) and extract_page in extract:
        extract = extract[extract_page]
    extract = {**extract, **g_eln_doc_specs}
    data = {}
    for field in eln_doc['fields']:
        if field['name'] in extract:
            data[field['name']] = field['content']
    for k in g_eln_doc_specs.keys():
        if k == 'owner':
            data[k] = '{} {}'.format(eln_doc[k]['firstName'], eln_doc[k]['lastName'])
        else:
            data[k] = str(eln_doc[k]).strip()
    return data, extract


def clean_up_eln_page_html(data_eln):
    data_clean_html = {}
    for k, v in data_eln.items():
        # Parse the HTML
        soup = BeautifulSoup(v, "html.parser")

        # 1. Remove all <style> and <link> tags
        for style_tag in soup(["style", "link"]):
            style_tag.decompose()

        # 2. Remove all inline 'style' attributes
        for tag in soup.find_all(True):
            if tag.has_attr('style'):
                del tag.attrs['style']

        # downgrade header elements <= h3 to h4
        # leave > h3 untouched for now
        pattern = re.compile(r"^h(\d)$")
        for tag in soup.find_all(pattern):
            if int(pattern.match(tag.name).group(1)) <= 3:
                # tag.name = "h%d" % (int(pattern.match(tag.name).group(1)) + 1)
                tag.name = "h4"

        # fix hrefs
        for a in soup.find_all('a', href=True):
            if not "http" in a['href']:
                a['href'] = "https://rspace.ntnu.no" + a['href']

        # fix img links
        for img in soup.find_all('img'):
            img['src'] = "https://rspace.ntnu.no" + img['src']

        data_clean_html[k] = soup.prettify()
    return data_clean_html

def gen_toc(toc_html, eln_pages):
    soup = BeautifulSoup(toc_html,'html.parser')
    article = soup.article
    eln_h3 = soup.new_tag("h3")
    article.append(eln_h3)
    eln_h3.string = "ELN entries"
    new_ul = soup.new_tag("ul")
    article.append(new_ul)
    for eln_page in eln_pages:
        _li = soup.new_tag("li")
        new_ul.append(_li)
        _a = soup.new_tag("a", href=eln_page)
        _li.append(_a)
    return soup.prettify()

def get_linked_images_from_eln(eln_doc, eln_client, tmp_folder=None):
    if tmp_folder is None:
        tmp_folder='tmp'
    files = {}
    for field in eln_doc['fields']:
        for file in field['files']:
            download_metadata_link = eln_client.get_link_contents(file, 'self')
            # check if image
            if 'image' in download_metadata_link['contentType']:
                filename = os.path.join(tmp_folder, "{}-{}".format(download_metadata_link['globalId'], download_metadata_link['name']))
                if not os.path.isdir('../tmp'):
                    os.mkdir('../tmp')
                eln_client.download_link_to_file(eln_client.get_link(download_metadata_link, 'enclosure'), filename)
                files[download_metadata_link['id']] = filename
    return files

def fix_img_links(eln_html_page, files):
    if files is None or len(files) == 0:
        return eln_html_page
    else:
        soup = BeautifulSoup(eln_html_page, 'html.parser')
        for img in soup.find_all('img'):
            for e in img['src'].split('&'):
                if 'sourceId=' in e:
                    _id = int(e.split('=')[1])
                    if _id in files:
                        img['src'] = files[_id]
                        if 'width' in img.attrs:
                            del img['width']
                        if 'height' in img.attrs:
                            del img['height']
        return soup.prettify()

def read_cfg(cfg_path):
    with open(cfg_path, "r") as f:
        cfg = json.load(f)
    return cfg

def make_outdir(target):
    tmp = 'tmp'
    tmp_folder = os.path.join(target, tmp)
    if os.path.isfile(target):
        print("output path exists but is not a folder")
        sys.exit(1)
    elif not os.path.exists(target):
        os.mkdir(target)
    if not os.path.isdir(tmp_folder):
        os.mkdir(tmp_folder)
    return tmp_folder

def get_elc_docs(eln_client, ids):
    docs = []
    for id in ids:
        docs.append(eln_client.get_document(id))
    return docs

def get_tmpl_files(tmpl_path):
    _fp = os.path.join(tmpl_path, 'files.json')
    if os.path.isfile(_fp):
        with open(_fp, 'r') as f:
            return json.load(f)

def check_tmpl_file(tmpl_path, file_n):
    if os.path.isfile(os.path.join(tmpl_path, file_n)):
        return True
    else:
        print(
            'template file {} is missing - exiting'.format(file_n))
        sys.exit(1)
        #return False

def get_template(template, run_dir):
    tmpl = {}
    _tmpl_path = None
    if template in g_report_templates:
        _tmpl_path = os.path.join(run_dir, g_report_templates[template])
        for k, v in get_tmpl_files(tmpl_path=_tmpl_path).items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if check_tmpl_file(_tmpl_path, vv):
                        tmpl[kk] = os.path.join(run_dir, g_report_templates[template], vv)
            else:
                if check_tmpl_file(_tmpl_path, v):
                    tmpl[k] = os.path.join(run_dir, g_report_templates[template], v)
    else:
        print('template {} not defined - exiting'.format(template))
        sys.exit(1)
    return tmpl, _tmpl_path

def generate_eln_page_html(eln_html, data, i, extract=None):
    if extract is None:
        extract = g_eln_extract
    eln_html_page = eln_html
    for k, v in data.items():
        if k == 'Date':
            v = v.strip()
        eln_html_page = eln_html_page.replace(extract[k], v)
    return eln_html_page.replace("$ELNID$", "eln-title-{}".format(i))

def process_main_page_html(main_html, data, extract, eln_html_pages, toptitle=None, sop_approver=None):
    main_html = main_html.replace("$ELNDOCS$", eln_html_pages)
    if toptitle:
        main_html = main_html.replace("$TITLE$", toptitle)
    if sop_approver:
        main_html = main_html.replace("$APPROVER$", sop_approver)
    for k, v in data.items():
        if k == 'Date':
            v = v.strip()
        main_html = main_html.replace(extract[k], v)
    return main_html

def get_doc_form_name(doc):
    return doc['form']['name']

def get_html_page(doc, tmpl_html):
    form_name = get_doc_form_name(doc)
    if form_name in tmpl_html:
        return tmpl_html[form_name], form_name
    else:
        return tmpl_html["report_eln_html"], None

def generate_pdf(tmpl_html, css_list, eln_doc, base_url, args, eln_ids=None):
    html_content = tmpl_html["report_html"]
    html_content = process_main_page_html(main_html=html_content, data=eln_doc.data, extract=eln_doc.extract,
                                          eln_html_pages=eln_doc.html, toptitle=args.title,
                                          sop_approver=args.sop_approver)
    if "report_toc_html" in tmpl_html and not eln_ids is None:
        toc_html = tmpl_html["report_toc_html"]
        toc_html = gen_toc(toc_html=toc_html, eln_pages=eln_ids)
        html_content = html_content.replace("$TOC$", toc_html)
    if args.title is None:
        out_file_name = sanitize_filename("{}.pdf".format(eln_doc.data['name'].replace("\n", "")), replacement_text='_')
    else:
        out_file_name = sanitize_filename("{}.pdf".format(args.title), replacement_text='_')
    HTML(string=html_content, base_url=base_url).write_pdf(os.path.join(args.output, out_file_name),
                                                           stylesheets=css_list)

    print("PDF '{}' generated successfully!".format(os.path.join(args.output, out_file_name)))


def main(args):
    cfg = read_cfg(cfg_path=args.rspace_cfg)
    eln_client = rspace_client.eln.eln.ELNClient(cfg["rspace_url"], cfg["rspace_apikey"])
    docs = get_elc_docs(eln_client=eln_client, ids=args.rspace_docs)
    tmp_folder = make_outdir(args.output)
    base_url = os.path.dirname(os.path.realpath(args.output))
    run_dir = os.path.dirname(os.path.realpath(__file__))
    tmpl, tmpl_p = get_template(template=args.template, run_dir=run_dir)
    tmpl_html = {}
    for k, v in tmpl.items():
        with open(v, 'r') as f:
            tmpl_html[k] = f.read()
    eln_docs = []
    files = {}
    for i, doc in enumerate(docs):
        eln_html, eln_page = get_html_page(doc, tmpl_html)
        data, extract = extract_data_from_eln(eln_doc=doc, extract=os.path.join(tmpl_p, 'extract.json'), extract_page=eln_page)
        data = clean_up_eln_page_html(data_eln=data)
        # get images
        files = files | get_linked_images_from_eln(eln_doc=doc, eln_client=eln_client, tmp_folder=tmp_folder)
        _eln_html_page = generate_eln_page_html(eln_html=eln_html, data=data, i=i, extract=extract)
        # TODO: the html returned from fix_img_links introduces a whitespace after the link to the RSpace document...
        eln_docs.append(Eln_data(id=i,
                                 html=fix_img_links(eln_html_page=_eln_html_page, files=files),
                                 data=data,
                                 extract=extract))

    if args.split:
        for eln_doc in eln_docs:
            generate_pdf(tmpl_html=tmpl_html, css_list=[CSS(filename=tmpl['report_css'])], eln_doc=eln_doc,
                         base_url=base_url,
                         args=args)
    else:
        # TODO: Using the last data and extract for the eln_doc is a bit hacky and can have missing data...
        # TODO: Add a way to provide global report information for the "one file" report from multiple ELN docs
        eln_doc = Eln_data(id=0,
                           html=''.join([d.html for d in eln_docs]),
                           data=eln_docs[-1].data,
                           extract=eln_docs[-1].extract)
        eln_ids = ["#eln-title-{}".format(d.id) for d in eln_docs]
        generate_pdf(tmpl_html=tmpl_html, css_list=[CSS(filename=tmpl['report_css'])], eln_doc=eln_doc,
                     base_url=base_url,
                     args=args, eln_ids=eln_ids)
    # clean tmp
    for k, file in files.items():
        try:
            if os.path.isfile(file):
                os.remove(file)
        except Exception as e:
            print(f'Failed to delete {file}. Reason: {e}')
    os.rmdir(tmp_folder)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MRCF / ISB / NTNU RSpace Documents to pretty PDFs Script to '
                                                 'generate a nice looking pdf for printing using entries from RSpace. '
                                                 'Script can generate one pdf document including a table of content '
                                                 'or individual pdfs from several RSpace documents.')
    parser.add_argument("--rspace_docs", nargs='+',
                        help="list of RSpace document IDs (SD..) example: SD12345 SD33333")
    parser.add_argument("--rspace_cfg", default=g_defaults['rspace_cfg'],
                        help="Path to json file with RSpace config (URL & API key) - default {}".format(g_defaults['rspace_cfg']))
    parser.add_argument("--title", default=g_defaults['title'],
                        help="Title for the generated pdf document")
    parser.add_argument("--sop_approver", default=g_defaults['sop_approver'],
                        help="Approver of the SOP. Only required for MRCF SOPs.")
    parser.add_argument("--template", default=g_defaults['template'],
                        help="Type of template to use - default {}".format(g_defaults['template']))
    parser.add_argument("output",
                        help="folder for output and temporary files")
    parser.add_argument("--split", dest='split', action='store_true',
                        help="The default is to generate one pdf from all provided RSpace docs. Use this flag to obtain one pdf per each RSpace document instead.")
    #parser.add_argument("-v", dest='verbose', action='store_true',
    #                    help="verbose mode - output a lot! info on screen")


    parser.set_defaults(verbose=False)
    parser.set_defaults(split=False)
    args = parser.parse_args()
    if len(args.rspace_docs) > 0:
        main(args=args)
    else:
        print('No input to shape into a report...exiting')