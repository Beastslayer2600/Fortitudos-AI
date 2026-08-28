Drop your product PDFs in this folder, then run:  python ingest.py

Suggested starting set:
  - Lifestyle Protector technical guide
  - Policy Protection ebook
  - Reg 28
  - BOI glossary
  - Product one-pagers

test-benefit-guide.pdf is a small sample with benefit-matrix tables.
Use it to confirm the stack works before adding real documents:

  python ingest.py
  python ask.py "what percentage is paid for hearing loss in both ears of 90 decibels or more"

Correct answer: 100%, with a 24 month waiting period.
If you get that back with a page citation, everything is wired up.
