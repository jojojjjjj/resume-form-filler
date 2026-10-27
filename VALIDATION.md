# Validation

This release uses generated fictional resumes and local HTML fixtures. It does not publish or test against the author's personal profile, applications, resume files, or active browser tabs.

The test suite covers PDF text extraction, encrypted/scanned PDF rejection, Word paragraphs/tables/headers, LaTeX includes and source-change detection, draft-to-reviewed profile persistence, profile backup, pending facts, project installation/upgrade, source and plan fingerprints, nonempty conflict handling, consent, sensitive controls, length limits, read-only controls, and repeatability.

The optional `tools/test.py --browser` uses a separate headless Chrome profile with a temporary localhost form. It exercises exact-tab binding, text/date/select/autocomplete controls, readback, idempotence, conflict protection, and module save evidence. No recruitment site or user browser profile is used. Ordinary CI runs offline fixtures without Chrome.

Release checks on Apple Silicon macOS: 30 offline tests passed; the isolated headless Chrome fixture passed; first-run project-local dependency installation and repeated invocation passed. The bootstrap has configurations for macOS, Linux glibc and Windows; CI tests Python 3.12 on macOS, Ubuntu and Windows. Runtime download/bootstrap on every OS/architecture, CAPTCHA, and arbitrary live hiring sites are outside the claimed validation scope.

PDF extraction is not OCR. Word text boxes and custom LaTeX macros can require manual/AI-assisted source review. The CLI text extractor does not autonomously infer a complete factual profile: the calling AI assistant structures and reviews the import before it can be used to fill forms.

Checkpoint `saved` records UI evidence of the save action, with `persistence_verified: false`; persistence must be checked by reading the website's stored fields/attachments. Tests of a local save button do not prove a hiring site's backend persistence.
