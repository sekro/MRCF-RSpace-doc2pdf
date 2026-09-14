# MRCF / ISB / NTNU RSpace Documents to pretty PDFs Script

Script for exporting documents from RSpace to nice looking PDFs for printing and use at the MR core facility at NTNU, Trondheim, Norway.

## Prepare the API access

API setup file:

- rspace.json

Paste your API key into this file and don't share that with others after :). See the RSpace doc on how to get your API key.


## Usage

`python MRCF_RSpace_doc2pdf.py folder_for_the_output_file --rspace_docs SD12345 SD54321 --title "A super nice looking report" --template mrcf_full`

### Detailed usage:

    usage: MRCF_RSpace_doc2pdf.py [-h] [--rspace_docs RSPACE_DOCS [RSPACE_DOCS ...]] [--rspace_cfg RSPACE_CFG] [--title TITLE] [--sop_approver SOP_APPROVER] [--template TEMPLATE] [--split] output

    MRCF / ISB / NTNU RSpace Documents to pretty PDFs Script to generate a nice looking pdf for printing using entries from RSpace. Script can generate one pdf document including a table of content or individual pdfs from several   
    RSpace documents.
    
    positional arguments:
      output                folder for output and temporary files
    
    options:
      -h, --help            show this help message and exit
      --rspace_docs RSPACE_DOCS [RSPACE_DOCS ...]
                            list of RSpace document IDs (SD..) example: SD12345 SD33333
      --rspace_cfg RSPACE_CFG
                            Path to json file with RSpace config (URL & API key) - default rspace.json
      --title TITLE         Title for the generated pdf document
      --sop_approver SOP_APPROVER
                            Approver of the SOP. Only required for MRCF SOPs.
      --template TEMPLATE   Type of template to use - default full
      --split               The default is to generate one pdf from all provided RSpace docs. Use this flag to obtain one pdf per each RSpace document instead.

### Available template options

- full : NTNU branded full report template incl table of content and title page (can be used as starting point for custome templates)
- mrcf_full : MRCF branded full report template incl table of content and title page
- mrcf_simple : MRCF branded simple template (best for individual RSpace documents)
- mrcf_sop : MRCF branded template for SOPs only. Provide SOP-approver via --sop_approver

Please note that use of NTNU logos requires your to follow NTNU's rules of use as detailed here: https://i.ntnu.no/wiki/-/wiki/Norsk/Bruksregler+for+NTNU-logoen 

### Output

One or multiple pdf files in the chosen output folder.