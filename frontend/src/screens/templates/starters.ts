// The example templates a new workspace starts from: copies of
// examples/cv.tex and examples/letter.tex (tests/templates.test.mjs keeps
// them equal). Small enough to ship with the screen.
import type { NewTemplate } from "../../query/templates";

export const EXAMPLE_CV: NewTemplate = {
  name: "Example CV",
  kind: "cv",
  is_default: false,
  guidance: "",
  rules: { max_pages: 1 },
  tex: `\\documentclass[10pt,a4paper]{article}
\\usepackage[margin=1.7cm]{geometry}
\\usepackage[T1]{fontenc}
\\usepackage{hyperref}
\\usepackage{iftex}
\\ifpdftex % pdfTeX only: searchable ligatures; Tectonic and XeTeX skip it
  \\input{glyphtounicode}
  \\pdfgentounicode=1
\\fi
\\pagestyle{empty}
\\setlength{\\parindent}{0pt}
\\begin{document}
{\\LARGE Alex Example}\\\\[3pt]
Backend Engineer \\hfill alex@example.test\\\\
\\href{https://example.test}{example.test}
\\section*{Profile}
Replace this synthetic summary using only the supplied career evidence.
\\section*{Experience}
\\textbf{Backend Engineer --- Example Cloud} \\hfill 2021--present
\\begin{itemize}
  \\item Built Python APIs and asynchronous workers for a developer platform.
  \\item Reduced API p95 latency by 20\\% through endpoint improvements and tracing.
\\end{itemize}
\\section*{Selected Project}
\\textbf{Reliable deployment workflow}
\\begin{itemize}
  \\item Reduced manual deployment steps from nine to three.
\\end{itemize}
\\section*{Skills}
Python, SQL, APIs, Docker, Linux.
\\end{document}
`,
};

export const EXAMPLE_LETTER: NewTemplate = {
  name: "Example letter",
  kind: "letter",
  is_default: false,
  guidance: "",
  rules: { max_pages: 1 },
  tex: `\\documentclass[11pt,a4paper]{article}
\\usepackage[margin=2.2cm]{geometry}
\\usepackage[T1]{fontenc}
\\usepackage{iftex}
\\ifpdftex % pdfTeX only: searchable ligatures; Tectonic and XeTeX skip it
  \\input{glyphtounicode}
  \\pdfgentounicode=1
\\fi
\\pagestyle{empty}
\\setlength{\\parindent}{0pt}
\\setlength{\\parskip}{0.8em}
\\begin{document}
{\\large Alex Example}\\\\
alex@example.test
\\bigskip
Dear Hiring Team,

Replace this synthetic example with a concise letter grounded in the supplied
career evidence and the selected job posting. Explain the connection through
specific relevant experience rather than unsupported claims.

Thank you for your consideration.

Alex Example
\\end{document}
`,
};
