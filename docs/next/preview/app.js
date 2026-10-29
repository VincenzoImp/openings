(() => {
  "use strict";
  const $ = (s) => document.querySelector(s),
    esc = (s) =>
      String(s ?? "").replace(
        /[&<>"']/g,
        (c) =>
          ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
          })[c],
      );
  const icons = {
    overview:
      '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    inbox: '<path d="M4 4h16v16H4z"/><path d="M4 14h5l2 3h2l2-3h5"/>',
    applications:
      '<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M8 5V3h8v2M3 11h18M9 11v9M15 11v9"/>',
    companies:
      '<path d="M5 21V3h12v18M17 9h3v12M2 21h20M8 7h1M13 7h1M8 11h1M13 11h1M8 15h1M13 15h1"/>',
    career: '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0116 0v2"/>',
    templates: '<path d="M6 3h9l4 4v14H6zM15 3v5h4M9 12h7M9 15h7M9 18h4"/>',
    settings:
      '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="var(--surface)"/><circle cx="15" cy="17" r="3" fill="var(--surface)"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    search: '<circle cx="10" cy="10" r="6"/><path d="M15 15l5 5"/>',
    close: '<path d="M6 6l12 12M6 18L18 6"/>',
    bookmark: '<path d="M6 3h12v18l-6-4-6 4z"/>',
    check: '<path d="M5 12l4 4L20 5"/>',
    arrow: '<path d="M5 12h14M14 7l5 5-5 5"/>',
    download: '<path d="M12 3v12M7 10l5 5 5-5M4 16v5h16v-5"/>',
    refresh:
      '<path d="M20 6v5h-5M4 18v-5h5"/><path d="M19 11a7 7 0 00-12-5L4 9M5 13a7 7 0 0012 5l3-3"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    file: '<path d="M5 3h9l5 5v13H5zM14 3v6h5M8 13h8M8 17h6"/>',
    link: '<path d="M10 14l4-4M8 16l-1 1a4 4 0 01-6-6l4-4a4 4 0 016 0M16 8l1-1a4 4 0 016 6l-4 4a4 4 0 01-6 0" transform="translate(1 0) scale(.9)"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    moon: '<path d="M20 14a8 8 0 01-10-10 8 8 0 1010 10"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1"/>',
    edit: '<path d="M15 4l5 5M4 20l2-6L17 3l4 4L10 18z"/>',
    board:
      '<rect x="3" y="4" width="5" height="16" rx="1"/><rect x="10" y="4" width="5" height="10" rx="1"/><rect x="17" y="4" width="4" height="13" rx="1"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    copy: '<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    trash: '<path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
    play: '<path d="M8 4l12 8-12 8z"/>',
  };
  const ico = (n, extra = "") =>
    `<svg class="icon ${extra}" viewBox="0 0 24 24" aria-hidden="true">${icons[n] || icons.file}</svg>`;
  const logo = (company, size = "") => {
    let c = companyColors[company] || ["#e5e5dc", "#59614f"];
    return `<span class="logo" ${size ? `style="${size}"` : ""} style="background:${c[0]};color:${c[1]}">${esc(company[0])}</span>`;
  };
  const companyColors = {
    "Northstar Labs": ["#dce6d9", "#55704b"],
    "Cedar Systems": ["#e5dfd5", "#7d705b"],
    "Arc Studio": ["#dfddea", "#70688e"],
    "Harbor Data": ["#dce5e9", "#5f7b86"],
    Fieldnote: ["#e6e4d8", "#7d7e51"],
    Orbit: ["#dde0eb", "#606f9c"],
    "Elm Technologies": ["#e2e8d8", "#697849"],
    Plainworks: ["#e9ddd9", "#9b6b5b"],
    "Rust & Byte": ["#e9e0d8", "#927653"],
    "Studio Pine": ["#e4e7dc", "#7c885d"],
  };
  const description = (role, stack) =>
    `About the role\nWe are looking for a ${role.toLowerCase()} who enjoys building reliable products with a thoughtful team. You will own meaningful work, collaborate across disciplines and help improve how we build.\n\nWhat you will do\n• Design and maintain ${stack}.\n• Work closely with product and engineering to turn ideas into dependable services.\n• Review code, document decisions and share what you learn.\n\nWhat you bring\nExperience delivering production software, clear communication and a practical approach to solving problems. Relevant hands-on experience matters more than checking every box.\n\nThis is a synthetic posting used only in the design preview.`;
  const initial = {
    profile: {
      name: "Alex Example",
      headline: "Backend engineer · APIs & dependable systems",
      location: "Zurich, Switzerland",
      email: "alex@example.test",
      roles: "Backend engineer, platform engineer, API engineer",
      preferences:
        "Remote or hybrid in Switzerland. Product-focused teams. Prefer Python and TypeScript.",
      summary:
        "Backend engineer with five years of experience building APIs and internal platforms. I enjoy clear contracts, practical infrastructure and making systems easier to operate.",
    },
    knowledge: [
      {
        id: "k1",
        title: "Backend engineer — Example Cloud",
        dates: "2021 – present",
        kind: "Experience",
        text: "Built and maintained Python APIs for an internal developer platform. Introduced request tracing and revised the most-used endpoints, reducing p95 latency by 20%. Worked with product and operations to move service ownership into small teams. Documented the rollout and trained four colleagues.",
      },
      {
        id: "k2",
        title: "A small, reliable deployment platform",
        dates: "2023",
        kind: "Project",
        text: "Designed a deployment workflow using typed configuration, automated health checks and rollback. The project made release status visible to the whole team and reduced manual deployment steps from nine to three.",
      },
    ],
    claims: [
      {
        id: "c1",
        text: "Reduced API p95 latency by 20% by revising core endpoints and adding request tracing.",
        evidence: "Backend engineer — Example Cloud",
        approved: true,
      },
      {
        id: "c2",
        text: "Reduced manual deployment steps from nine to three with a typed release workflow.",
        evidence: "A small, reliable deployment platform",
        approved: true,
      },
      {
        id: "c3",
        text: "Helped four colleagues take ownership of production services through documentation and training.",
        evidence: "Backend engineer — Example Cloud",
        approved: false,
      },
    ],
    jobs: [
      {
        id: "j1",
        title: "Senior Backend Engineer",
        company: "Northstar Labs",
        location: "Zurich · Hybrid",
        salary: "CHF 115–135k",
        source: "Greenhouse",
        date: "Today",
        score: 92,
        outdated: false,
        triage: "inbox",
        posting: description(
          "Senior Backend Engineer",
          "Python APIs and event-driven services",
        ),
        note: "",
      },
      {
        id: "j2",
        title: "API Engineer",
        company: "Cedar Systems",
        location: "Remote · Europe",
        salary: "€85–110k",
        source: "Lever",
        date: "Today",
        score: 86,
        outdated: true,
        triage: "inbox",
        posting: description(
          "API Engineer",
          "public APIs and developer tooling",
        ),
        note: "The API ownership looks particularly relevant.",
      },
      {
        id: "j3",
        title: "Infrastructure Engineer",
        company: "Arc Studio",
        location: "Basel · Hybrid",
        salary: "CHF 110–130k",
        source: "Ashby",
        date: "Yesterday",
        score: 82,
        outdated: false,
        triage: "inbox",
        posting: description(
          "Infrastructure Engineer",
          "internal platforms and delivery systems",
        ),
        note: "",
      },
      {
        id: "j4",
        title: "Backend Engineer",
        company: "Harbor Data",
        location: "Remote",
        salary: "Not specified",
        source: "Manual",
        date: "Yesterday",
        score: null,
        outdated: false,
        triage: "inbox",
        posting: "",
        note: "",
      },
      {
        id: "j5",
        title: "Platform Engineer",
        company: "Fieldnote",
        location: "Zurich · Hybrid",
        salary: "CHF 115–130k",
        source: "Greenhouse",
        date: "Oct 26",
        score: 88,
        outdated: false,
        triage: "saved",
        posting: description(
          "Platform Engineer",
          "developer workflows and Python services",
        ),
        note: "",
      },
      {
        id: "j6",
        title: "Backend Engineer",
        company: "Orbit",
        location: "Remote · Europe",
        salary: "€90–115k",
        source: "Lever",
        date: "Oct 24",
        score: 89,
        outdated: false,
        triage: "saved",
        posting: description(
          "Backend Engineer",
          "TypeScript services and APIs",
        ),
        note: "",
      },
      {
        id: "j7",
        title: "Python Engineer",
        company: "Cedar Systems",
        location: "Zurich · Hybrid",
        salary: "CHF 110–125k",
        source: "Lever",
        date: "Oct 20",
        score: 91,
        outdated: false,
        triage: "saved",
        posting: description("Python Engineer", "Python product services"),
        note: "",
      },
      {
        id: "j8",
        title: "Infrastructure Engineer",
        company: "Elm Technologies",
        location: "Bern · Hybrid",
        salary: "CHF 120–140k",
        source: "Ashby",
        date: "Oct 18",
        score: 90,
        outdated: false,
        triage: "saved",
        posting: description("Infrastructure Engineer", "platform automation"),
        note: "",
      },
      {
        id: "j9",
        title: "API Developer",
        company: "Northstar Labs",
        location: "Zurich",
        salary: "CHF 100–120k",
        source: "Greenhouse",
        date: "Oct 12",
        score: 84,
        outdated: false,
        triage: "saved",
        posting: description("API Developer", "customer-facing APIs"),
        note: "",
      },
      {
        id: "j10",
        title: "Backend Engineer",
        company: "Plainworks",
        location: "Zurich · Hybrid",
        salary: "CHF 115–130k",
        source: "Ashby",
        date: "Oct 8",
        score: 93,
        outdated: false,
        triage: "saved",
        posting: description("Backend Engineer", "Python services"),
        note: "",
      },
      {
        id: "j11",
        title: "Developer Tools Engineer",
        company: "Rust & Byte",
        location: "Remote · Europe",
        salary: "€90–120k",
        source: "Manual",
        date: "Oct 22",
        score: 87,
        outdated: false,
        triage: "saved",
        posting: description(
          "Developer Tools Engineer",
          "developer tooling and internal APIs",
        ),
        note: "",
      },
      {
        id: "j12",
        title: "QA Automation Engineer",
        company: "Studio Pine",
        location: "Munich",
        salary: "Not specified",
        source: "Lever",
        date: "Oct 15",
        score: 48,
        outdated: false,
        triage: "dismissed",
        posting: description(
          "QA Automation Engineer",
          "automated testing systems",
        ),
        note: "Set aside: location and role focus.",
      },
    ],
    applications: [
      {
        id: "a1",
        jobId: "j5",
        stage: "draft",
        date: "Oct 27",
        history: ["draft"],
        outcome: null,
      },
      {
        id: "a2",
        jobId: "j6",
        stage: "applied",
        date: "Oct 25",
        history: ["applied"],
        outcome: null,
      },
      {
        id: "a3",
        jobId: "j7",
        stage: "interview",
        date: "Oct 22",
        history: ["applied", "interview"],
        outcome: null,
      },
      {
        id: "a4",
        jobId: "j8",
        stage: "offer",
        date: "Oct 20",
        history: ["applied", "interview", "offer"],
        outcome: null,
      },
      {
        id: "a5",
        jobId: "j9",
        stage: "closed",
        date: "Oct 14",
        history: ["applied"],
        outcome: "rejected",
      },
      {
        id: "a6",
        jobId: "j10",
        stage: "closed",
        date: "Oct 10",
        history: ["applied", "interview", "offer"],
        outcome: "accepted",
      },
      {
        id: "a7",
        jobId: "j11",
        stage: "applied",
        date: "Oct 24",
        history: ["applied"],
        outcome: null,
      },
    ],
    companies: [
      {
        id: "co1",
        name: "Northstar Labs",
        ats: "Greenhouse",
        board: "northstarlabs",
        url: "https://boards.greenhouse.io/northstarlabs",
        enabled: true,
        count: 2,
        last: "Today, 07:00",
        schedule: "Daily at 07:00",
      },
      {
        id: "co2",
        name: "Cedar Systems",
        ats: "Lever",
        board: "cedarsystems",
        url: "https://jobs.lever.co/cedarsystems",
        enabled: true,
        count: 2,
        last: "Today, 07:00",
        schedule: "Daily at 07:00",
      },
      {
        id: "co3",
        name: "Arc Studio",
        ats: "Ashby",
        board: "arcstudio",
        url: "https://jobs.ashbyhq.com/arcstudio",
        enabled: false,
        count: 1,
        last: "Yesterday, 07:00",
        schedule: "Daily at 07:00",
      },
    ],
    templates: [
      {
        id: "t1",
        name: "Editorial CV",
        kind: "Resume",
        default: true,
        revision: 1,
        append:
          "Use a concise summary. Prefer concrete outcomes over lists of duties. Keep the document to two pages.",
        max: 180,
        pages: 2,
      },
      {
        id: "t2",
        name: "Compact CV",
        kind: "Resume",
        default: false,
        revision: 1,
        append:
          "One page. Choose only the most relevant experiences and approved claims.",
        max: 150,
        pages: 1,
      },
      {
        id: "t3",
        name: "Cover letter",
        kind: "Letter",
        default: true,
        revision: 1,
        append:
          "Use a clear opening and two concrete examples. Avoid generic praise and exaggerated enthusiasm.",
        max: 300,
        pages: 1,
      },
    ],
    guidance:
      "Use only facts supported by my career knowledge. You may select approved claims or write new wording from detailed evidence. Keep the language direct and specific. Ask about missing information instead of inventing it. Save the PDF and the filled sources as a new draft.",
    settings: {
      scoring: false,
      mode: "local",
      endpoint: "http://scorer:8000",
      model: "english",
      periodic: false,
      rubric:
        "Assess how well the candidate’s stated skills, experience and preferences match the core responsibilities and requirements of this job. Missing information is unknown, not proof of a match. Return an indicative fit level; do not judge writing style.",
    },
    activity: [
      {
        title: "Interview recorded",
        detail: "Cedar Systems · Python Engineer",
        time: "Yesterday",
        icon: "applications",
      },
      {
        title: "New opportunities collected",
        detail: "Northstar Labs and Cedar Systems",
        time: "Today, 07:00",
        icon: "inbox",
      },
      {
        title: "CV and source uploaded",
        detail: "Fieldnote · Platform Engineer",
        time: "Oct 27",
        icon: "file",
      },
    ],
    theme: "light",
  };
  const key = "openings-design-preview-v1";
  let state;
  try {
    state = JSON.parse(localStorage.getItem(key)) || structuredClone(initial);
  } catch {
    state = structuredClone(initial);
  }
  let route = location.hash.slice(1) || "overview",
    triage = "inbox",
    query = "",
    companyFilter = "",
    sort = "fit",
    appView = "board",
    careerTab = "profile",
    settingsTab = "scoring",
    templateId = "t1",
    drawer = null,
    drawerTab = "posting",
    lastFocus = null;
  const stages = ["draft", "applied", "interview", "offer", "closed"],
    stageName = {
      draft: "Draft",
      applied: "Applied",
      interview: "Interview",
      offer: "Offer",
      closed: "Closed",
    },
    navs = [
      ["overview", "Overview"],
      ["inbox", "Inbox"],
      ["applications", "Applications"],
      ["companies", "Companies"],
      ["career", "Career"],
      ["templates", "Templates"],
      ["settings", "Settings"],
    ];
  const persist = () => {
    try {
      localStorage.setItem(key, JSON.stringify(state));
    } catch {
      toast("Demo storage is full; this change remains in memory.");
    }
  };
  function toast(text) {
    $("#toast").textContent = text;
    $("#toast").classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => $("#toast").classList.remove("show"), 3600);
  }
  function addActivity(title, detail, icon = "edit") {
    state.activity.unshift({ title, detail, time: "Just now · demo", icon });
    state.activity = state.activity.slice(0, 6);
    persist();
  }
  function head(title, subtitle, action = "") {
    return `<header class="pagehead"><div><div class="eyebrow">Your workspace</div><h1>${title}</h1><p>${subtitle}</p></div><div class="actions">${action}</div></header>`;
  }
  function render() {
    document.documentElement.dataset.theme = state.theme;
    $("#app").innerHTML =
      `<div class="app-shell"><div class="mobile-shade" onclick="UI.menu(false)"></div><aside class="sidebar"><a class="brand" href="#overview" aria-label="Openings overview"><span class="brandmark" aria-hidden="true"></span><span class="brandname">Openings</span></a><div class="workspace-label">Personal workspace</div><nav class="nav" aria-label="Main navigation">${navs.map(([id, name]) => `<a href="#${id}" class="${route === id ? "active" : ""}" ${route === id ? 'aria-current="page"' : ""}>${ico(id)}${name}${id === "inbox" ? `<span class="navcount">${state.jobs.filter((j) => j.triage === "inbox").length}</span>` : ""}</a>`).join("")}</nav><div class="sidebar-bottom"><div class="sidebar-note"><b>Your search, in one place.</b><br>Knowledge, opportunities and the work you put into them.</div><button class="btn subtle small" style="margin:0 5px 15px" onclick="UI.reset()">${ico("refresh")} Reset preview</button><div class="user"><span class="avatar">AE</span><div class="usercopy"><strong>${esc(state.profile.name)}</strong><br><span class="muted">Personal workspace</span></div><button class="iconbtn" aria-label="Toggle color theme" onclick="UI.theme()">${ico(state.theme === "light" ? "moon" : "sun")}</button></div></div></aside><main class="main"><div class="topbar"><div class="breadcrumb"><button class="iconbtn mobile-menu" aria-label="Open navigation" onclick="UI.menu(true)">${ico("menu")}</button><span>Workspace</span><span>/</span>${navs.find((n) => n[0] === route)?.[1] || "Overview"}</div><div class="topbar-right"><span class="prototype-label">Design preview · synthetic data</span><button class="iconbtn" title="About this preview" aria-label="About this preview" onclick="UI.about()">${ico("info")}</button></div></div><div class="content" id="page">${page()}</div></main></div>`;
  }
  function page() {
    return (
      { overview, inbox, applications, companies, career, templates, settings }[
        route
      ] || overview
    )();
  }
  function overview() {
    let sent = state.applications.filter((a) => a.history.includes("applied")),
      interviews = sent.filter((a) => a.history.includes("interview")),
      offers = sent.filter((a) => a.history.includes("offer")),
      active = sent.filter((a) => a.stage !== "closed");
    let out = state.jobs.filter(
        (j) => j.outdated && j.triage !== "dismissed",
      ).length,
      needs = state.jobs.filter(
        (j) => !j.posting && j.triage !== "dismissed",
      ).length,
      drafts = state.applications.filter((a) => a.stage === "draft").length;
    return (
      head(
        "Your search, at a glance.",
        "A clear view of your opportunities and the progress you are making.",
        `<span class="muted smalltext" style="margin-right:8px">Thursday, October 29</span><button class="btn primary" onclick="UI.addJob()">${ico("plus")} Add job</button>`,
      ) +
      `<div class="stats">${[
        [sent.length, "Applications sent", "All recorded attempts", "applied"],
        [
          interviews.length,
          "Reached interview",
          "A conversation worth having",
          "interview",
        ],
        [
          offers.length,
          "Offers received",
          "Progress through the funnel",
          "offer",
        ],
        [
          active.length,
          "In progress",
          "Currently awaiting a next step",
          "draft",
        ],
      ]
        .map(
          ([n, l, f, c]) =>
            `<section class="card stat"><div class="stat-top">${l}<span class="dot ${c}"></span></div><div class="stat-value">${n}</div><div class="stat-foot">${f}</div></section>`,
        )
        .join(
          "",
        )}</div><section class="card"><div class="cardhead"><div><h2>Your application journey</h2><p>Where submitted applications progressed, and where they stand now.</p></div><span class="tag neutral">All time</span></div><div class="funnel-wrap">${funnel(sent)}</div><div class="funnel-legend"><span><i class="dot applied"></i>Applied</span><span><i class="dot interview"></i>Interview</span><span><i class="dot offer"></i>Offer</span><span><i class="dot"></i>Accepted</span><span><i class="dot closed"></i>Closed or waiting</span></div><details class="funnel-table"><summary>View counts as a table</summary><table><tbody><tr><td>Submitted attempts</td><td>${sent.length}</td></tr><tr><td>Reached interview</td><td>${interviews.length}</td></tr><tr><td>Received an offer</td><td>${offers.length}</td></tr><tr><td>Accepted</td><td>${sent.filter((a) => a.outcome === "accepted").length}</td></tr><tr><td>Still in progress</td><td>${active.length}</td></tr></tbody></table></details></section><div class="grid-2"><section class="card"><div class="cardhead"><h2>Worth a look</h2><span class="tag neutral">${[drafts > 0, out > 0, needs > 0].filter(Boolean).length} things</span></div><div class="inner">${drafts ? `<button class="taskrow" onclick="UI.go('applications')"><span class="circle">${ico("file")}</span><span class="taskcopy"><strong>${drafts} application ${drafts === 1 ? "draft is" : "drafts are"} ready to review</strong><small>Your documents stay here until you decide what comes next.</small></span><span class="arrow">↗</span></button>` : ""}${out ? `<button class="taskrow" onclick="UI.go('inbox')"><span class="circle">${ico("refresh")}</span><span class="taskcopy"><strong>${out} ${out === 1 ? "score needs" : "scores need"} updating</strong><small>Your profile changed. Nothing was rescored automatically.</small></span><span class="arrow">↗</span></button>` : ""}${needs ? `<button class="taskrow" onclick="UI.openJob('j4')"><span class="circle">${ico("inbox")}</span><span class="taskcopy"><strong>${needs} job ${needs === 1 ? "needs" : "need"} the full posting</strong><small>Paste the text to complete the record.</small></span><span class="arrow">↗</span></button>` : ""}${!drafts && !out && !needs ? "<p>You are all caught up.</p>" : ""}</div></section><section class="card"><div class="cardhead"><h2>Recent activity</h2><button class="btn subtle small" onclick="UI.go('applications')">View applications ${ico("arrow")}</button></div><div class="inner">${state.activity
        .slice(0, 3)
        .map(
          (a) =>
            `<div class="activity"><span class="activity-icon">${ico(a.icon)}</span><div><strong>${esc(a.title)}</strong><p>${esc(a.detail)}</p><time>${esc(a.time)}</time></div></div>`,
        )
        .join("")}</div></section></div>`
    );
  }
  function funnel(sent) {
    let interviews = sent.filter((a) => a.history.includes("interview")),
      offers = sent.filter((a) => a.history.includes("offer")),
      accepted = offers.filter((a) => a.outcome === "accepted"),
      waiting = sent.filter(
        (a) => !a.history.includes("interview") && a.stage !== "closed",
      ),
      rejected = sent.filter(
        (a) => !a.history.includes("interview") && a.stage === "closed",
      ),
      atInterview = interviews.filter((a) => !a.history.includes("offer")),
      atOffer = offers.filter((a) => a.outcome !== "accepted");
    let unit = sent.length ? Math.min(24, 180 / sent.length) : 24;
    const band = (x, y, xx, yy, h, color, opacity = 0.4) =>
      h
        ? `<path d="M${x} ${y} C${(x + xx) / 2} ${y} ${(x + xx) / 2} ${yy} ${xx} ${yy} L${xx} ${yy + h} C${(x + xx) / 2} ${yy + h} ${(x + xx) / 2} ${y + h} ${x} ${y + h}Z" fill="${color}" opacity="${opacity}"/>`
        : "";
    const node = (x, y, n, label, color) =>
      `<rect x="${x}" y="${y}" width="5" height="${Math.max(n * unit, 2)}" rx="2" fill="${color}"/><text class="node-label" x="${x}" y="${y - 47}">${label}</text><text class="node-count" x="${x}" y="${y - 17}">${n}</text>`;
    return `<svg class="funnel-svg" viewBox="0 0 1000 400" role="img" aria-label="Application funnel: ${sent.length} applied, ${interviews.length} reached interview, ${offers.length} received offers, ${accepted.length} accepted"><path d="M45 310H950" stroke="var(--line)" stroke-dasharray="3 5" fill="none"/>${band(50, 88, 345, 88, interviews.length * unit, "#a3adba")}${band(50, 88 + interviews.length * unit, 345, 270, waiting.length * unit, "#bcc3c6", 0.28)}${band(50, 88 + (interviews.length + waiting.length) * unit, 345, 355, rejected.length * unit, "#bb9e92", 0.3)}${band(350, 88, 640, 88, offers.length * unit, "#b5a3bb")}${band(350, 88 + offers.length * unit, 640, 270, atInterview.length * unit, "#b9adc0", 0.28)}${band(645, 88, 935, 88, accepted.length * unit, "#b9bf9e")}${band(645, 88 + accepted.length * unit, 935, 270, atOffer.length * unit, "#cbbb8f", 0.3)}${node(45, 88, sent.length, "Applied", "#8d9daf")}${node(345, 88, interviews.length, "Interview", "#a492b0")}${node(640, 88, offers.length, "Offer", "#bba06c")}${node(935, 88, accepted.length, "Accepted", "#83936f")}<rect x="345" y="270" width="5" height="${Math.max(2, waiting.length * unit)}" rx="2" fill="#aab2b2"/><text x="360" y="286">${waiting.length} waiting</text><rect x="345" y="355" width="5" height="${Math.max(2, rejected.length * unit)}" rx="2" fill="#b6968a"/><text x="360" y="370">${rejected.length} closed after applying</text><rect x="640" y="270" width="5" height="${Math.max(2, atInterview.length * unit)}" rx="2" fill="#aa9cb3"/><text x="655" y="286">${atInterview.length} at interview stage</text><rect x="935" y="270" width="5" height="${Math.max(2, atOffer.length * unit)}" rx="2" fill="#bba06c"/><text x="910" y="310" text-anchor="end">${atOffer.length} deciding</text></svg>`;
  }
  function filteredJobs() {
    let rows = state.jobs.filter(
      (j) =>
        j.triage === triage &&
        (!companyFilter || j.company === companyFilter) &&
        `${j.title} ${j.company} ${j.location} ${j.posting}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    );
    if (sort === "fit") rows.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
    if (sort === "company")
      rows.sort((a, b) => a.company.localeCompare(b.company));
    return rows;
  }
  function score(j) {
    return j.score === null
      ? '<span class="muted smalltext">Unscored</span>'
      : `<span class="score ${j.outdated ? "outdated" : ""}">${j.score}<span class="muted" style="font-size:9px;font-weight:400">fit</span></span>${j.outdated ? '<span class="tag amber">Outdated</span>' : ""}`;
  }
  function jobRows() {
    let rows = filteredJobs();
    return rows.length
      ? `<div class="card joblist">${rows.map((j) => `<article class="jobrow" tabindex="0" role="button" aria-label="Open ${esc(j.title)} at ${esc(j.company)}" onclick="UI.openJob('${j.id}')" onkeydown="if(event.key==='Enter')UI.openJob('${j.id}')">${logo(j.company)}<div><div class="jobtitle">${esc(j.title)}</div><div class="jobmeta">${esc(j.company)}<span class="sep">·</span>${esc(j.source)}${!j.posting ? '<span class="tag amber">Needs text</span>' : ""}</div></div><div class="location-col"><div class="date">${esc(j.location)}</div><div class="date" style="font-size:9px;margin-top:4px">${esc(j.salary)}</div></div><div class="scorebox">${score(j)}</div><button class="iconbtn" aria-label="${j.triage === "saved" ? "Open saved job" : "Save job"}" onclick="event.stopPropagation();UI.triage('${j.id}','saved')">${ico("bookmark")}</button></article>`).join("")}</div>`
      : '<div class="card empty"><h2>A little breathing room.</h2><p>No jobs match these filters.</p><button class="btn" onclick="UI.clearFilters()">Clear filters</button></div>';
  }
  function inbox() {
    return (
      head(
        "Your opportunities.",
        "A considered shortlist starts with a well-kept inbox.",
        `<button class="btn primary" onclick="UI.addJob()">${ico("plus")} Add job</button>`,
      ) +
      `<div class="tabs" role="tablist" aria-label="Job triage">${[
        ["inbox", "To review"],
        ["saved", "Saved"],
        ["dismissed", "Dismissed"],
      ]
        .map(
          ([v, l]) =>
            `<button role="tab" aria-selected="${triage === v}" class="tab ${triage === v ? "active" : ""}" onclick="UI.setTriage('${v}')">${l}<span class="counter">${state.jobs.filter((j) => j.triage === v).length}</span></button>`,
        )
        .join(
          "",
        )}</div><div class="toolbar"><label class="search">${ico("search")}<input id="job-search" aria-label="Search jobs" placeholder="Search jobs, companies or keywords" value="${esc(query)}" oninput="UI.search(this.value)"></label><select aria-label="Filter by company" onchange="UI.filterCompany(this.value)"><option value="">All companies</option>${[
        ...new Set(state.jobs.map((j) => j.company)),
      ]
        .sort()
        .map(
          (c) =>
            `<option ${companyFilter === c ? "selected" : ""}>${esc(c)}</option>`,
        )
        .join(
          "",
        )}</select><span class="spacer"></span><span class="smalltext muted">Sort by</span><select aria-label="Sort jobs" onchange="UI.sort(this.value)"><option value="fit" ${sort === "fit" ? "selected" : ""}>Highest fit</option><option value="recent" ${sort === "recent" ? "selected" : ""}>Recently added</option><option value="company" ${sort === "company" ? "selected" : ""}>Company</option></select></div><div id="job-results">${jobRows()}</div><div class="list-footer"><span id="job-count">${filteredJobs().length} opportunities</span><span>Scores are indicative · ${state.settings.scoring ? "Scoring enabled" : "Automatic scoring is off"}</span></div>`
    );
  }
  function applications() {
    return (
      head(
        "Keep the whole picture.",
        "Documents, conversations and decisions — each in its place.",
        `<div class="segmented" aria-label="Application view"><button class="${appView === "board" ? "active" : ""}" onclick="UI.appView('board')">${ico("board")} Board</button><button class="${appView === "list" ? "active" : ""}" onclick="UI.appView('list')">${ico("list")} List</button></div>`,
      ) +
      `<div class="toolbar"><span class="smalltext muted">${state.applications.length} application attempts</span><span class="spacer"></span><span class="smalltext muted">${appView === "board" ? "Drag a card to change its stage, or open it to edit." : "Each application keeps its own documents and history."}</span></div>${
        appView === "board"
          ? `<div class="kanban">${stages
              .map(
                (s) =>
                  `<section class="column" ondragover="event.preventDefault();this.classList.add('dragover')" ondragleave="this.classList.remove('dragover')" ondrop="event.preventDefault();UI.moveApp(event.dataTransfer.getData('text/plain'),'${s}')"><div class="colhead"><i class="dot ${s}"></i>${stageName[s]}<span>${state.applications.filter((a) => a.stage === s).length}</span></div>${state.applications
                    .filter((a) => a.stage === s)
                    .map((a) => appCard(a))
                    .join("")}</section>`,
              )
              .join("")}</div>`
          : `<div class="card table-wrap"><table class="table"><thead><tr><th>Role / company</th><th>Stage</th><th>Started</th><th>Documents</th></tr></thead><tbody>${state.applications
              .map((a) => {
                let j = state.jobs.find((j) => j.id === a.jobId);
                return `<tr tabindex="0" onclick="UI.openApp('${a.id}')" onkeydown="if(event.key==='Enter')UI.openApp('${a.id}')"><td><strong style="font-weight:500">${esc(j.title)}</strong><br><span class="muted smalltext">${esc(j.company)}</span></td><td><span class="status-label"><i class="dot ${a.stage}"></i>${stageName[a.stage]}${a.outcome ? ` · ${a.outcome}` : ""}</span></td><td class="muted">${a.date}</td><td class="muted">${a.empty ? "No files yet" : "CV + sources"}</td></tr>`;
              })
              .join("")}</tbody></table></div>`
      }<p class="hint">Creating or uploading documents does not mark an application as sent. Record the stage when it actually changes.</p>`
    );
  }
  function appCard(a) {
    let j = state.jobs.find((j) => j.id === a.jobId);
    return `<article class="application-card" draggable="true" ondragstart="event.dataTransfer.setData('text/plain','${a.id}')" onclick="UI.openApp('${a.id}')" tabindex="0" role="button" aria-label="Open application for ${esc(j.title)} at ${esc(j.company)}" onkeydown="if(event.key==='Enter')UI.openApp('${a.id}')"><div class="app-company">${logo(j.company)}${esc(j.company)}</div><h3>${esc(j.title)}</h3>${a.outcome ? `<span class="tag ${a.outcome === "accepted" ? "green" : "neutral"}" style="margin-top:9px">${a.outcome === "accepted" ? "Accepted" : "Not selected"}</span>` : ""}<div class="app-foot"><span>${ico("file")} ${a.empty ? "0" : "2"} files</span><span>${a.date}</span></div></article>`;
  }
  function companies() {
    return (
      head(
        "Follow the teams you like.",
        "Collect openings directly from the companies you choose.",
        `<button class="btn primary" onclick="UI.addCompany()">${ico("plus")} Add company</button>`,
      ) +
      `<div class="companygrid">${state.companies.map((c) => `<section class="card companycard"><div class="companytop">${logo(c.name)}<div><h3>${esc(c.name)}</h3><p>${esc(c.ats)} board</p></div><button class="switch" role="switch" aria-label="Collect jobs from ${esc(c.name)}" aria-checked="${c.enabled}" onclick="UI.toggleCompany('${c.id}')"></button></div><span class="tag ${c.enabled ? "green" : "neutral"}">${c.enabled ? "Collecting" : "Paused"}</span><dl class="company-facts"><div><dt>Stored jobs</dt><dd>${state.jobs.filter((j) => j.company === c.name).length}</dd></div><div><dt>Last collection</dt><dd style="font-size:10px">${esc(c.last)}</dd></div></dl><p class="smalltext">${esc(c.schedule)}</p><div class="companybottom"><button class="btn subtle small" onclick="UI.companyJobs('${c.name}')">View jobs ${ico("arrow")}</button><button class="btn small" onclick="UI.runCompany('${c.id}')">${ico("refresh")} Run now</button></div></section>`).join("")}</div><div class="note" style="margin-top:22px">${ico("info")}<span>Pausing a source keeps its jobs, notes and application history. You can always add a job manually or through your agent.</span></div>`
    );
  }
  function career() {
    return (
      head(
        "Your experience, in full.",
        "The knowledge behind your applications — richer than a résumé.",
      ) +
      `<div class="tabs" role="tablist" aria-label="Career section">${[
        ["profile", "Profile"],
        ["knowledge", "Career knowledge"],
        ["claims", "Reusable claims"],
      ]
        .map(
          ([id, name]) =>
            `<button class="tab ${careerTab === id ? "active" : ""}" role="tab" aria-selected="${careerTab === id}" onclick="UI.careerTab('${id}')">${name}</button>`,
        )
        .join(
          "",
        )}</div><div class="reading-width">${careerTab === "profile" ? profileForm() : careerTab === "knowledge" ? knowledge() : claims()}</div>`
    );
  }
  function profileForm() {
    let p = state.profile;
    return `<form class="card sectioncard" onsubmit="event.preventDefault();UI.saveProfile(this)"><div class="sectiontitle"><div><h2>A useful introduction</h2><p>Facts and preferences that help you and your agent choose well.</p></div><span class="manual-tag">Editable knowledge</span></div><div class="formgrid">${[
      ["name", "Full name"],
      ["headline", "Headline"],
      ["location", "Location"],
      ["email", "Email"],
    ]
      .map(
        ([id, l]) =>
          `<label class="field"><span>${l}</span><input name="${id}" value="${esc(p[id])}"></label>`,
      )
      .join(
        "",
      )}<label class="field full"><span>Roles you are looking for</span><input name="roles" value="${esc(p.roles)}"></label><label class="field full"><span>Work preferences</span><textarea name="preferences" rows="3">${esc(p.preferences)}</textarea></label><label class="field full"><span>Professional summary</span><textarea name="summary" rows="4">${esc(p.summary)}</textarea></label></div><div class="section-footer"><span>Relevant changes mark scores outdated. They do not launch rescoring.</span><button class="btn primary" type="submit">Save profile</button></div></form>`;
  }
  function knowledge() {
    return `<div class="actions" style="justify-content:space-between;margin-bottom:18px"><p class="smalltext">Detailed context, outcomes and the story behind them.</p><button class="btn" onclick="UI.editKnowledge()">${ico("plus")} Add entry</button></div>${state.knowledge.map((k) => `<section class="card knowledge-card"><div class="knowledge-head"><div><span class="eyebrow">${esc(k.kind)}</span><h3>${esc(k.title)}</h3><p>${esc(k.dates)}</p></div><button class="iconbtn" aria-label="Edit ${esc(k.title)}" onclick="UI.editKnowledge('${k.id}')">${ico("edit")}</button></div><p class="narrative">${esc(k.text)}</p><div class="actions" style="margin-top:19px"><span class="tag neutral">Narrative evidence</span><span class="tag neutral">${state.claims.filter((c) => c.evidence === k.title).length} linked claims</span></div></section>`).join("")}`;
  }
  function claims() {
    return `<div class="actions" style="justify-content:space-between;margin-bottom:18px"><p class="smalltext">Short statements your agent can reuse, backed by detailed evidence.</p><button class="btn" onclick="UI.addClaim()">${ico("plus")} Add claim</button></div><div class="card">${state.claims.map((c) => `<div class="claimrow"><div class="claimcopy"><p>${esc(c.text)}</p><small>${esc(c.evidence)}</small></div><span class="tag ${c.approved ? "green" : "amber"}">${c.approved ? "Approved" : "Draft"}</span><button class="btn small" onclick="UI.approveClaim('${c.id}')">${c.approved ? "Mark draft" : "Approve"}</button></div>`).join("")}</div><p class="hint">Claims are reusable wording, not the whole knowledge base. An agent can also describe experience directly from the underlying evidence.</p>`;
  }
  const texSource = String.raw`\documentclass[11pt,a4paper]{article}
\usepackage[margin=1.8cm]{geometry}
\usepackage{hyperref}
\begin{document}
\begin{center}
  {\LARGE Alex Example}\\
  Backend Engineer · Zurich, Switzerland
\end{center}
\section*{Experience}
% The agent fills this document using career evidence.
% Keep the original reusable template separate.
\begin{itemize}
  \item Reduced API latency by 20\% through tracing and endpoint improvements.
\end{itemize}
\end{document}`;
  function templates() {
    let t =
      state.templates.find((t) => t.id === templateId) || state.templates[0];
    return (
      head(
        "A good starting point.",
        "Your templates and instructions, ready for you or your agent.",
        `<label class="btn">${ico("plus")} Add template<input class="filepick" type="file" accept=".tex,.zip,.md" onchange="UI.importTemplate(this.files[0])"></label>`,
      ) +
      `<div class="templates-layout"><div class="template-list">${state.templates.map((t) => `<button class="template-option ${t.id === templateId ? "active" : ""}" onclick="UI.template('${t.id}')"><span class="template-banner"><span class="mini-page"><i class="mini-line"></i><i class="mini-line"></i><i class="mini-line"></i><i class="mini-line"></i><i class="mini-line"></i></span></span><strong>${esc(t.name)}</strong><small>${t.kind} · LaTeX · revision ${t.revision}</small><span class="tag ${t.default ? "green" : "neutral"}">${t.default ? "Default " + t.kind.toLowerCase() : "Alternative"}</span></button>`).join("")}</div><div><section class="card template-editor"><div class="cardhead" style="padding-bottom:18px"><div><h2>${esc(t.name)}</h2><p>Reusable source and template-specific guidance.</p></div>${!t.default ? `<button class="btn small" onclick="UI.setDefaultTemplate('${t.id}')">Set as default</button>` : '<span class="tag green">Default</span>'}</div><div class="paperpreview"><article class="cvpaper"><h2>ALEX EXAMPLE</h2><div class="cvcontact">Backend Engineer · Zurich, Switzerland · alex@example.test</div><p>Backend engineer building dependable APIs and clear developer experiences.</p><h3>Experience</h3><div class="cvrole"><span>Example Cloud</span><span>2021–present</span></div><p>Backend Engineer</p><ul><li>Reduced API p95 latency by 20% through endpoint improvements and request tracing.</li><li>Helped four colleagues take ownership of production services.</li></ul><h3>Selected project</h3><div class="cvrole"><span>Deployment platform</span><span>2023</span></div><ul><li>Reduced manual deployment steps from nine to three with a typed workflow.</li></ul><h3>Skills</h3><p>Python · TypeScript · API design · SQL · Observability</p><h3>Education</h3><p>Example University · BSc, Computer Science</p></article></div><div class="inner"><p class="smalltext">Illustrative layout · actual PDF compilation happens outside the app.</p><details style="margin-top:18px"><summary class="inline-link" style="cursor:pointer">View and edit LaTeX source</summary><textarea id="template-source" class="source-editor" style="margin-top:12px" aria-label="Template LaTeX source">${esc(t.source || texSource)}</textarea></details></div></section><form class="card sectioncard" style="margin-top:20px" onsubmit="event.preventDefault();UI.saveTemplate(this,'${t.id}')"><div class="sectiontitle"><h2>Writing instructions</h2></div><label class="field"><span>General guidance</span><textarea name="general" rows="4">${esc(state.guidance)}</textarea><small>Available to the external agent for every document.</small></label><label class="field" style="margin-top:20px"><span>Additional instructions for ${esc(t.name)}</span><textarea name="append" rows="3">${esc(t.append)}</textarea></label><div class="formgrid" style="margin-top:20px"><label class="field"><span>Bullet character target</span><input type="number" min="40" max="500" name="max" value="${t.max}"></label><label class="field"><span>Page target</span><input type="number" min="1" max="6" name="pages" value="${t.pages}"></label></div><div class="section-footer"><span>Saving instructions creates a new template revision, not a new CV.</span><button class="btn primary" type="submit">Save instructions</button></div></form></div></div>`
    );
  }
  function settings() {
    return (
      head(
        "Make it work for you.",
        "A small set of controls, with deliberate defaults.",
      ) +
      `<div class="tabs" role="tablist" aria-label="Settings section">${[
        ["scoring", "AI scoring"],
        ["agents", "Agent access"],
        ["workspace", "Workspace"],
      ]
        .map(
          ([id, name]) =>
            `<button role="tab" aria-selected="${settingsTab === id}" class="tab ${settingsTab === id ? "active" : ""}" onclick="UI.settingsTab('${id}')">${name}</button>`,
        )
        .join(
          "",
        )}</div><div class="reading-width">${settingsTab === "scoring" ? scoringSettings() : settingsTab === "agents" ? agentSettings() : workspaceSettings()}</div>`
    );
  }
  function scoringSettings() {
    let s = state.settings;
    return `<form class="card sectioncard" onsubmit="event.preventDefault();UI.saveScoring(this)"><div class="settingrow"><div><h3>Enable AI scoring</h3><p>Assess new opportunities against your experience and preferences.</p></div><button type="button" class="switch" role="switch" aria-label="Enable AI scoring" aria-checked="${s.scoring}" onclick="UI.toggleScoring()"></button></div><div class="radio-cards"><label class="radio-card"><input type="radio" name="mode" value="local" ${s.mode === "local" ? "checked" : ""} onchange="UI.scoringMode('local')"><span><strong>Local service</strong><small>One optional CPU model on this host.</small></span></label><label class="radio-card"><input type="radio" name="mode" value="remote" ${s.mode === "remote" ? "checked" : ""} onchange="UI.scoringMode('remote')"><span><strong>Remote service</strong><small>Your compatible endpoint on another host.</small></span></label></div><div class="formgrid"><label class="field"><span>Service URL</span><input name="endpoint" type="url" required value="${esc(s.endpoint)}"></label><label class="field"><span>Served model</span><input name="model" required value="${esc(s.model)}"><small>${s.mode === "local" ? "Laya English is the working CPU preset." : "Select a model available on your endpoint."}</small></label></div><label class="field" style="margin-top:21px"><span>Assessment instructions</span><textarea name="rubric" rows="4">${esc(s.rubric)}</textarea><small>The rubric is separate from CV-writing instructions.</small></label><div class="divider"></div><div class="settingrow"><div><h3>Periodically update outdated scores</h3><p>Off by default. Profile edits never start a bulk rescore.</p></div><button type="button" class="switch" role="switch" aria-label="Periodic rescoring" aria-checked="${s.periodic}" onclick="UI.togglePeriodic()"></button></div><div class="section-footer"><span>Existing scores remain visible when scoring is off.</span><button class="btn primary" type="submit">Save scoring settings</button></div></form><div class="note">${ico("info")}<span>${s.scoring ? "Scoring is enabled in this design preview. No endpoint is contacted and no model runs." : "The workspace works without a model. Collection, search, documents and tracking stay available."}</span></div>`;
  }
  function agentSettings() {
    return `<section class="card sectioncard"><div class="sectiontitle"><div><h2>Your agent, your tools.</h2><p>The app keeps the context. Your external agent does the writing and compilation.</p></div></div><label class="field"><span>Example MCP endpoint</span><span class="endpoint">http://localhost:8080/mcp<button class="iconbtn" aria-label="Copy example MCP endpoint" onclick="UI.copy('http://localhost:8080/mcp')">${ico("copy")}</button></span></label>${[
      [
        "Connect your assistant",
        "Configure this workspace in Codex, Claude Code or another MCP client.",
      ],
      [
        "Read the right context",
        "The agent retrieves career evidence, the job, template and your stored instructions.",
      ],
      [
        "Prepare externally, keep the results here",
        "The agent compiles on its own machine and uploads PDF, sources and answers for review.",
      ],
    ]
      .map(
        ([title, body], i) =>
          `<div class="step"><span class="stepnum">${i + 1}</span><div><strong>${title}</strong><p>${body}</p></div></div>`,
      )
      .join(
        "",
      )}<div class="section-footer"><span>Example connection details only; no MCP server runs in this preview.</span><button class="btn" onclick="UI.agentBrief()">${ico("file")} See agent brief</button></div></section><div class="note">${ico("info")}<span>The companion skill explains the workflow. The actual MCP tools remain self-describing and usable without it.</span></div>`;
  }
  function workspaceSettings() {
    return `<section class="card sectioncard"><div class="sectiontitle"><h2>Workspace</h2></div><div class="settingrow"><div><h3>Interface language</h3><p>English. Your own profile, templates and documents can use any language.</p></div><span class="tag neutral">English</span></div><div class="settingrow"><div><h3>Appearance</h3><p>Quiet surfaces, legible text and comfortable contrast.</p></div><button class="btn" onclick="UI.theme()">${ico(state.theme === "light" ? "moon" : "sun")} ${state.theme === "light" ? "Dark mode" : "Light mode"}</button></div><div class="settingrow"><div><h3>Demo data</h3><p>Export the synthetic browser state for this preview.</p></div><button class="btn" onclick="UI.exportDemo()">${ico("download")} Export demo JSON</button></div><div class="settingrow"><div><h3>Reset preview</h3><p>Restore the original synthetic examples in this browser.</p></div><button class="btn danger" onclick="UI.reset()">Reset</button></div></section><p class="hint">The production workspace will use SQLite backup and restore. This design preview stores changes only in this browser.</p>`;
  }
  function showModal(html) {
    lastFocus = document.activeElement;
    $("#overlay").innerHTML =
      `<div class="overlay-shade" onclick="UI.close()"></div><section class="modal" role="dialog" aria-modal="true"><button class="iconbtn close" aria-label="Close dialog" onclick="UI.close()">${ico("close")}</button>${html}</section>`;
    requestAnimationFrame(() =>
      $(".modal input,.modal textarea,.modal button:not(.close)")?.focus(),
    );
  }
  function close() {
    drawer = null;
    $("#overlay").innerHTML = "";
    lastFocus?.focus?.();
  }
  function drawerShell(html, foot = "") {
    lastFocus = document.activeElement;
    $("#overlay").innerHTML =
      `<div class="overlay-shade" onclick="UI.close()"></div><section class="drawer" role="dialog" aria-modal="true">${html}${foot ? `<div class="drawerfoot">${foot}</div>` : ""}</section>`;
    requestAnimationFrame(() => $(".drawer button")?.focus());
  }
  function openJob(id) {
    let j = state.jobs.find((j) => j.id === id);
    if (!j) {
      toast("This demo job is no longer in the workspace.");
      return;
    }
    drawer = { type: "job", id };
    drawerTab = "posting";
    drawJob();
  }
  function drawJob() {
    let j = state.jobs.find((j) => j.id === drawer.id);
    if (!j) return;
    drawerShell(
      `<header class="drawerhead"><button class="iconbtn close" aria-label="Close job" onclick="UI.close()">${ico("close")}</button>${logo(j.company)}<h2>${esc(j.title)}</h2><div class="jobmeta">${esc(j.company)}<span>·</span>${esc(j.location)}</div><div class="tabs" role="tablist">${[
        ["posting", "Posting"],
        ["notes", "Notes"],
        ["edit", "Edit details"],
      ]
        .map(
          ([id, name]) =>
            `<button class="tab ${drawerTab === id ? "active" : ""}" onclick="UI.drawerTab('${id}')">${name}</button>`,
        )
        .join(
          "",
        )}</div></header><div class="drawercontent">${drawerTab === "posting" ? `<dl class="detailfacts"><div><dt>Fit assessment</dt><dd>${score(j)}</dd></div><div><dt>Source</dt><dd>${esc(j.source)}</dd></div><div><dt>Compensation</dt><dd>${esc(j.salary)}</dd></div><div><dt>Saved in workspace</dt><dd>${esc(j.date)}</dd></div></dl>${j.posting ? `<div class="posting">${esc(j.posting)}</div>` : `<div class="note">${ico("info")}<span>The full posting is missing. Paste it under Edit details to complete this job.</span></div>`}` : drawerTab === "notes" ? `<form onsubmit="event.preventDefault();UI.saveNote(this)"><label class="field"><span>Your private notes</span><textarea name="note" rows="11" placeholder="What stands out? Questions to ask?">${esc(j.note)}</textarea></label><button class="btn primary" style="margin-top:15px">Save note</button></form>` : `<form onsubmit="event.preventDefault();UI.saveJob(this)"><div class="stack"><label class="field"><span>Role</span><input name="title" required value="${esc(j.title)}"></label><label class="field"><span>Company</span><input name="company" required value="${esc(j.company)}"></label><label class="field"><span>Location</span><input name="location" value="${esc(j.location)}"></label><label class="field"><span>Posting text</span><textarea name="posting" rows="10">${esc(j.posting)}</textarea></label><button class="btn primary">Save details</button></div></form>`}</div>`,
      `<button class="btn subtle small danger" onclick="UI.forget('${j.id}')">${ico("trash")} Forget</button><div class="actions">${j.triage === "dismissed" ? `<button class="btn" onclick="UI.triage('${j.id}','inbox')">Restore to inbox</button>` : `<button class="btn" onclick="UI.triage('${j.id}','dismissed')">Dismiss</button><button class="btn ${j.triage === "saved" ? "" : "primary"}" onclick="UI.triage('${j.id}','saved')">${ico("bookmark")} ${j.triage === "saved" ? "Saved" : "Save job"}</button><button class="btn ${j.triage === "saved" ? "primary" : ""}" onclick="UI.createApplication('${j.id}')">Create application</button>`}</div>`,
    );
  }
  function openApp(id) {
    let a = state.applications.find((a) => a.id === id);
    if (!a) return;
    drawer = { type: "application", id };
    drawerTab = "documents";
    drawApp();
  }
  function drawApp() {
    let a = state.applications.find((a) => a.id === drawer.id),
      j = state.jobs.find((j) => j.id === a.jobId);
    drawerShell(
      `<header class="drawerhead"><button class="iconbtn close" aria-label="Close application" onclick="UI.close()">${ico("close")}</button><span class="eyebrow">Application</span><h2>${esc(j.title)}</h2><div class="jobmeta">${esc(j.company)}<span>·</span>${esc(j.location)}</div><div style="margin-top:18px;display:flex;align-items:center;gap:12px"><span class="smalltext muted">Stage</span><select aria-label="Application stage" style="width:145px;padding:7px 10px;font-size:11px" onchange="UI.moveApp('${a.id}',this.value)">${stages.map((s) => `<option value="${s}" ${s === a.stage ? "selected" : ""}>${stageName[s]}</option>`).join("")}</select></div><div class="tabs">${[
        ["documents", "Documents"],
        ["answers", "Form answers"],
        ["history", "History"],
      ]
        .map(
          ([id, name]) =>
            `<button class="tab ${drawerTab === id ? "active" : ""}" onclick="UI.drawerTab('${id}')">${name}</button>`,
        )
        .join("")}</div></header><div class="drawercontent">${
        drawerTab === "documents"
          ? a.empty
            ? `<div class="empty" style="padding:35px 10px"><h2>A clean starting point.</h2><p>Your agent can prepare documents using this application's context, then upload PDF and sources here.</p><div class="actions" style="justify-content:center;margin-top:20px"><button class="btn" onclick="UI.exportContext('${a.id}')">${ico("download")} Export context</button><label class="btn">${ico("plus")} Upload PDF<input class="filepick" type="file" accept=".pdf" onchange="UI.uploadDocument(this.files[0])"></label></div></div>`
            : `<div class="documentrow">${ico("file")}<div class="doccopy"><strong>${esc(a.uploaded?.name || "Alex_Example_CV.pdf")}</strong><small>Draft · external compilation · synthetic example</small></div><a class="iconbtn" aria-label="Download example PDF" href="${a.uploaded?.url || "assets/example-cv.pdf"}" download>${ico("download")}</a></div><div class="documentrow">${ico("file")}<div class="doccopy"><strong>application.tex</strong><small>Filled source · revision 1</small></div><button class="iconbtn" aria-label="Download filled source" onclick="UI.downloadSource()">${ico("download")}</button></div><div class="actions" style="margin:17px 0"><label class="btn">${ico("plus")} Upload document<input class="filepick" type="file" accept=".pdf,.tex,.txt,.md" onchange="UI.uploadDocument(this.files[0])"></label><button class="btn" onclick="UI.exportContext('${a.id}')">${ico("download")} Export context</button></div><p class="smalltext muted">Preview of an externally compiled example PDF.</p><iframe title="Example CV PDF preview" class="pdf-preview" src="${a.uploaded?.url || "assets/example-cv.pdf"}#toolbar=0"></iframe>`
          : drawerTab === "answers"
            ? `<form onsubmit="event.preventDefault();UI.saveAnswers(this)"><label class="field"><span>Why are you interested in this role?</span><textarea name="why" rows="5">${esc(a.answers?.why || "I enjoy building dependable services and clear API contracts. This role connects closely with my experience improving Python APIs and developer workflows.")}</textarea><small>Maximum 800 characters</small></label><label class="field" style="margin-top:20px"><span>What are your salary expectations?</span><textarea name="salary" rows="3">${esc(a.answers?.salary || "Open to discussing a package that reflects the role and responsibilities.")}</textarea></label><button class="btn primary" style="margin-top:18px">Save answers</button></form>`
            : `<div class="stack">${[...(a.events || [])]
                .reverse()
                .map(
                  (e) =>
                    `<div class="activity"><span class="activity-icon">${ico("edit")}</span><div><strong>${esc(e)}</strong><time>Just now · demo</time></div></div>`,
                )
                .join("")}${[...a.history]
                .reverse()
                .map(
                  (s) =>
                    `<div class="activity"><span class="activity-icon"><i class="dot ${s}"></i></span><div><strong>${stageName[s]} recorded</strong><p>This stage is part of the synthetic example history.</p><time>${a.date}</time></div></div>`,
                )
                .join("")}</div>`
      }</div>`,
      `<span class="smalltext muted">${a.stage === "draft" ? "Draft — not sent" : "Progress recorded manually"}</span><button class="btn" onclick="UI.agentBrief('${a.id}')">${ico("copy")} Agent brief</button>`,
    );
  }
  function markOutdated() {
    state.jobs.forEach((j) => {
      if (j.score !== null) j.outdated = true;
    });
  }
  function download(name, content, type = "text/plain") {
    let url = URL.createObjectURL(new Blob([content], { type })),
      a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
  const UI = {
    go(id) {
      location.hash = id;
      if (route === id) {
        render();
        close();
      }
    },
    menu(open) {
      $(".sidebar").classList.toggle("open", open);
      $(".mobile-shade").classList.toggle("open", open);
    },
    theme() {
      state.theme = state.theme === "light" ? "dark" : "light";
      persist();
      render();
    },
    about() {
      showModal(
        '<h2>A working design preview.</h2><p>All records are synthetic. Interactions are stored in this browser only. This preview does not run collection, scoring, MCP, a database or a document compiler.</p><p>Use it to explore the information structure and daily workflow before the production application is built.</p><div class="actions"><button class="btn primary" onclick="UI.close()">Continue exploring</button></div>',
      );
    },
    reset() {
      if (confirm("Reset the synthetic preview data in this browser?")) {
        state = structuredClone(initial);
        persist();
        query = "";
        companyFilter = "";
        close();
        render();
        toast("Preview reset.");
      }
    },
    close,
    openJob,
    openApp,
    setTriage(v) {
      triage = v;
      render();
    },
    search(v) {
      query = v;
      $("#job-results").innerHTML = jobRows();
      $("#job-count").textContent = `${filteredJobs().length} opportunities`;
    },
    filterCompany(v) {
      companyFilter = v;
      render();
    },
    sort(v) {
      sort = v;
      render();
    },
    clearFilters() {
      query = "";
      companyFilter = "";
      render();
    },
    appView(v) {
      appView = v;
      render();
    },
    careerTab(v) {
      careerTab = v;
      render();
    },
    settingsTab(v) {
      settingsTab = v;
      render();
    },
    template(v) {
      templateId = v;
      render();
    },
    drawerTab(v) {
      drawerTab = v;
      drawer?.type === "job" ? drawJob() : drawApp();
    },
    triage(id, value) {
      let j = state.jobs.find((j) => j.id === id);
      if (!j) return;
      j.triage = value;
      addActivity(
        value === "dismissed"
          ? "Job dismissed"
          : value === "saved"
            ? "Job saved"
            : "Job restored",
        `${j.company} · ${j.title}`,
        "bookmark",
      );
      render();
      if (drawer?.type === "job") drawJob();
      toast(
        value === "dismissed"
          ? "Dismissed — history is kept."
          : value === "saved"
            ? "Saved to your shortlist."
            : "Restored to the inbox.",
      );
    },
    addJob() {
      showModal(
        `<h2>Add an opportunity.</h2><p>Keep a job you found, however you found it.</p><form onsubmit="event.preventDefault();UI.submitJob(this)"><label class="field"><span>Job URL</span><input name="url" type="url" placeholder="https://company.example/careers/role"></label><div class="formgrid"><label class="field"><span>Role</span><input name="title" required placeholder="Backend Engineer"></label><label class="field"><span>Company</span><input name="company" required placeholder="Company name"></label></div><label class="field" style="margin-top:15px"><span>Posting text</span><textarea name="posting" rows="5" placeholder="Paste the posting here…"></textarea><small>No page is fetched in this offline preview. A URL-only entry stays incomplete.</small></label><div class="actions"><button type="button" class="btn" onclick="UI.close()">Cancel</button><button class="btn primary">Add to inbox</button></div></form>`,
      );
    },
    submitJob(form) {
      let f = new FormData(form),
        url = f.get("url").trim(),
        posting = f.get("posting").trim();
      if (!url && !posting) {
        toast("Add a URL or paste the posting text.");
        return;
      }
      let existing = url && state.jobs.find((j) => j.url === url);
      if (existing) {
        close();
        openJob(existing.id);
        toast("This URL is already in the demo workspace.");
        return;
      }
      let j = {
        id: "j" + Date.now(),
        title: f.get("title").trim(),
        company: f.get("company").trim(),
        url,
        posting,
        location: "Not specified",
        salary: "Not specified",
        date: "Just now",
        source: "Manual",
        score: null,
        outdated: false,
        triage: "inbox",
        note: "",
      };
      state.jobs.unshift(j);
      triage = "inbox";
      query = "";
      companyFilter = "";
      addActivity("Job added manually", `${j.company} · ${j.title}`, "inbox");
      close();
      if (route !== "inbox") location.hash = "inbox";
      else render();
      toast("Added to the demo inbox.");
    },
    saveNote(form) {
      let j = state.jobs.find((j) => j.id === drawer.id);
      j.note = new FormData(form).get("note");
      persist();
      toast("Note saved in this browser.");
    },
    saveJob(form) {
      let j = state.jobs.find((j) => j.id === drawer.id),
        f = new FormData(form);
      for (let name of ["title", "company", "location", "posting"])
        j[name] = f.get(name).trim();
      if (j.score !== null) j.outdated = true;
      persist();
      render();
      drawJob();
      toast("Details saved. Existing score marked outdated.");
    },
    forget(id) {
      let j = state.jobs.find((j) => j.id === id),
        n = state.applications.filter((a) => a.jobId === id).length;
      showModal(
        `<h2>Forget this job?</h2><p>This removes ${esc(j.title)} at ${esc(j.company)} from the demo, including its notes and ${n} application ${n === 1 ? "attempt" : "attempts"}. It will not be remembered as dismissed.</p><p>If acquired again, it can be a new job. This action cannot be undone in the preview.</p><div class="actions"><button class="btn" onclick="UI.close()">Cancel</button><button class="btn primary" onclick="UI.confirmForget('${id}')">Forget job</button></div>`,
      );
    },
    confirmForget(id) {
      state.jobs = state.jobs.filter((j) => j.id !== id);
      state.applications = state.applications.filter((a) => a.jobId !== id);
      persist();
      close();
      render();
      toast("Job and related demo records removed.");
    },
    createApplication(id) {
      let existing = state.applications.find(
        (a) => a.jobId === id && a.stage !== "closed",
      );
      if (existing) {
        openApp(existing.id);
        return;
      }
      let j = state.jobs.find((j) => j.id === id);
      j.triage = "saved";
      let a = {
        id: "a" + Date.now(),
        jobId: id,
        stage: "draft",
        date: "Just now",
        history: ["draft"],
        outcome: null,
        empty: true,
      };
      state.applications.push(a);
      addActivity(
        "Application draft created",
        `${j.company} · ${j.title}`,
        "applications",
      );
      render();
      openApp(a.id);
      toast("Created a draft. No documents were generated.");
    },
    moveApp(id, stage) {
      let a = state.applications.find((a) => a.id === id);
      if (!a || !stages.includes(stage)) return;
      let old = a.stage;
      if (old === stage) return;
      a.stage = stage;
      if (stage !== "closed" && !a.history.includes(stage))
        a.history.push(stage);
      if (stage === "closed" && !a.outcome) a.outcome = "not_pursued";
      if (stage !== "closed") a.outcome = null;
      (a.events ??= []).push(
        `Stage changed from ${stageName[old]} to ${stageName[stage]}`,
      );
      let j = state.jobs.find((j) => j.id === a.jobId);
      addActivity(
        "Application stage updated",
        `${j.company} · ${stageName[stage]}`,
        "applications",
      );
      render();
      if (drawer?.type === "application") drawApp();
      toast(`Moved to ${stageName[stage]}.`);
    },
    toggleCompany(id) {
      let c = state.companies.find((c) => c.id === id);
      c.enabled = !c.enabled;
      persist();
      render();
      toast(
        c.enabled
          ? "Source enabled in the preview."
          : "Source paused. Stored jobs are kept.",
      );
    },
    runCompany(id) {
      let c = state.companies.find((c) => c.id === id);
      c.last = "Just now · demo";
      persist();
      render();
      toast("Simulated collection only — no live board was contacted.");
    },
    companyJobs(name) {
      companyFilter = name;
      query = "";
      triage = "inbox";
      location.hash = "inbox";
      if (route === "inbox") render();
    },
    addCompany() {
      showModal(
        `<h2>Follow a company.</h2><p>Use a supported ATS board to keep its openings together.</p><form onsubmit="event.preventDefault();UI.submitCompany(this)"><label class="field"><span>Company name</span><input name="name" required placeholder="Example company"></label><label class="field"><span>Career or ATS URL</span><input type="url" name="url" required placeholder="https://jobs.ashbyhq.com/example" oninput="UI.detectATS(this.form)"></label><div class="formgrid"><label class="field"><span>ATS platform</span><select name="ats"><option>Greenhouse</option><option>Lever</option><option>Ashby</option></select></label><label class="field"><span>Board identifier</span><input name="board" required placeholder="example"></label></div><p class="hint">URLs are not fetched in this offline preview. New sources start paused.</p><div class="actions"><button type="button" class="btn" onclick="UI.close()">Cancel</button><button class="btn primary">Save company</button></div></form>`,
      );
    },
    detectATS(form) {
      try {
        let u = new URL(form.url.value);
        if (u.host.includes("ashby")) form.ats.value = "Ashby";
        if (u.host.includes("lever")) form.ats.value = "Lever";
        if (u.host.includes("greenhouse")) form.ats.value = "Greenhouse";
        form.board.value = u.pathname.split("/").filter(Boolean)[0] || "";
      } catch {}
    },
    submitCompany(form) {
      let f = new FormData(form);
      state.companies.push({
        id: "co" + Date.now(),
        name: f.get("name"),
        url: f.get("url"),
        ats: f.get("ats"),
        board: f.get("board"),
        enabled: false,
        last: "Not collected",
        schedule: "Daily at 07:00",
      });
      persist();
      close();
      render();
      toast("Company saved in the preview, initially paused.");
    },
    saveProfile(form) {
      let f = new FormData(form),
        old = JSON.stringify([
          state.profile.headline,
          state.profile.location,
          state.profile.roles,
          state.profile.preferences,
          state.profile.summary,
        ]);
      for (let name of Object.keys(state.profile))
        state.profile[name] = f.get(name);
      let next = JSON.stringify([
        state.profile.headline,
        state.profile.location,
        state.profile.roles,
        state.profile.preferences,
        state.profile.summary,
      ]);
      if (next !== old) markOutdated();
      addActivity("Profile updated", "No scores were recalculated.", "career");
      render();
      toast(
        next !== old
          ? "Profile saved. Old scores marked outdated; no rescoring started."
          : "Profile saved.",
      );
    },
    editKnowledge(id) {
      let k = state.knowledge.find((k) => k.id === id) || {
        id: "",
        title: "",
        dates: "",
        kind: "Experience",
        text: "",
      };
      showModal(
        `<h2>${id ? "Edit career knowledge." : "Add career knowledge."}</h2><p>Keep the detailed story, not only the résumé bullet.</p><form onsubmit="event.preventDefault();UI.saveKnowledge(this,'${k.id}')"><label class="field"><span>Title / organization</span><input name="title" required value="${esc(k.title)}"></label><label class="field"><span>Dates</span><input name="dates" value="${esc(k.dates)}" placeholder="2021 – present"></label><label class="field"><span>Detailed evidence</span><textarea name="text" required rows="7">${esc(k.text)}</textarea></label><div class="actions"><button class="btn" type="button" onclick="UI.close()">Cancel</button><button class="btn primary">Save knowledge</button></div></form>`,
      );
    },
    saveKnowledge(form, id) {
      let f = new FormData(form),
        k = state.knowledge.find((k) => k.id === id);
      if (!k) {
        k = { id: "k" + Date.now(), kind: "Experience" };
        state.knowledge.push(k);
      }
      Object.assign(k, {
        title: f.get("title"),
        dates: f.get("dates"),
        text: f.get("text"),
      });
      markOutdated();
      persist();
      close();
      render();
      toast("Knowledge saved. Scores were not recalculated.");
    },
    approveClaim(id) {
      let c = state.claims.find((c) => c.id === id);
      c.approved = !c.approved;
      markOutdated();
      persist();
      render();
      toast(c.approved ? "Claim approved." : "Claim marked as draft.");
    },
    addClaim() {
      showModal(
        `<h2>Add a reusable claim.</h2><p>Connect a concise statement to the evidence behind it.</p><form onsubmit="event.preventDefault();UI.submitClaim(this)"><label class="field"><span>Claim</span><textarea name="text" required rows="4"></textarea></label><label class="field"><span>Supporting knowledge</span><select name="evidence">${state.knowledge.map((k) => `<option>${esc(k.title)}</option>`).join("")}</select></label><div class="actions"><button type="button" class="btn" onclick="UI.close()">Cancel</button><button class="btn primary">Save as draft</button></div></form>`,
      );
    },
    submitClaim(form) {
      let f = new FormData(form);
      state.claims.push({
        id: "c" + Date.now(),
        text: f.get("text"),
        evidence: f.get("evidence"),
        approved: false,
      });
      persist();
      close();
      render();
      toast("Draft claim saved for review.");
    },
    setDefaultTemplate(id) {
      let t = state.templates.find((t) => t.id === id);
      state.templates.forEach((x) => {
        if (x.kind === t.kind) x.default = x.id === id;
      });
      persist();
      render();
      toast("Default template updated.");
    },
    saveTemplate(form, id) {
      let t = state.templates.find((t) => t.id === id),
        f = new FormData(form);
      state.guidance = f.get("general");
      t.append = f.get("append");
      t.max = Number(f.get("max"));
      t.pages = Number(f.get("pages"));
      t.source = $("#template-source")?.value || t.source;
      t.revision++;
      persist();
      render();
      toast("Instructions saved. Scores and previous documents are unchanged.");
    },
    importTemplate(file) {
      if (!file) return;
      let t = {
        id: "t" + Date.now(),
        name: file.name.replace(/\.[^.]+$/, ""),
        kind: "Resume",
        default: false,
        revision: 1,
        append: "",
        max: 180,
        pages: 2,
      };
      state.templates.push(t);
      templateId = t.id;
      if (file.name.endsWith(".tex"))
        file.text().then((text) => {
          t.source = text;
          persist();
          render();
        });
      persist();
      render();
      toast("Template added to demo data; no compilation was run.");
    },
    toggleScoring() {
      state.settings.scoring = !state.settings.scoring;
      persist();
      render();
    },
    togglePeriodic() {
      state.settings.periodic = !state.settings.periodic;
      persist();
      render();
    },
    scoringMode(mode) {
      state.settings.mode = mode;
      state.settings.endpoint =
        mode === "local"
          ? "http://scorer:8000"
          : "http://model-host.example:8000";
      state.settings.model = mode === "local" ? "english" : "my-served-model";
      persist();
      render();
    },
    saveScoring(form) {
      let f = new FormData(form),
        s = state.settings,
        changed =
          s.endpoint !== f.get("endpoint") ||
          s.model !== f.get("model") ||
          s.rubric !== f.get("rubric");
      s.endpoint = f.get("endpoint");
      s.model = f.get("model");
      s.rubric = f.get("rubric");
      if (changed) markOutdated();
      persist();
      render();
      toast("Settings saved locally. No endpoint was contacted.");
    },
    saveAnswers(form) {
      let a = state.applications.find((a) => a.id === drawer.id),
        f = new FormData(form);
      a.answers = { why: f.get("why"), salary: f.get("salary") };
      persist();
      toast("Form answers saved as draft content.");
    },
    uploadDocument(file) {
      if (!file) return;
      let a = state.applications.find((a) => a.id === drawer.id);
      if (!a) return;
      if (file.type !== "application/pdf") {
        toast(
          "Source selected: " +
            file.name +
            ". This preview displays PDF uploads only.",
        );
        return;
      }
      if (file.size > 800000) {
        toast("Use a PDF below 800 KB for browser-only preview storage.");
        return;
      }
      let reader = new FileReader();
      reader.onload = () => {
        a.empty = false;
        a.uploaded = { name: file.name, url: reader.result };
        (a.events ??= []).push("Uploaded " + file.name);
        persist();
        drawApp();
        toast("PDF uploaded into browser demo storage.");
      };
      reader.readAsDataURL(file);
    },
    exportContext(id) {
      let a = state.applications.find((a) => a.id === id),
        j = state.jobs.find((j) => j.id === a.jobId);
      download(
        "example-application-context.json",
        JSON.stringify(
          {
            prototype: true,
            synthetic: true,
            application: a,
            job: j,
            profile: state.profile,
            evidence: state.knowledge,
            claims: state.claims.filter((c) => c.approved),
            template: state.templates.find(
              (t) => t.default && t.kind === "Resume",
            ),
            generalInstructions: state.guidance,
          },
          null,
          2,
        ),
        "application/json",
      );
      toast("Synthetic context downloaded; no inference was run.");
    },
    downloadSource() {
      download("application.tex", texSource, "application/x-tex");
    },
    exportDemo() {
      download(
        "openings-synthetic-preview.json",
        JSON.stringify(state, null, 2),
        "application/json",
      );
      toast("Demo JSON exported.");
    },
    agentBrief(id) {
      let a = id && state.applications.find((a) => a.id === id),
        j = a && state.jobs.find((j) => j.id === a.jobId),
        brief = `Prepare a draft application${j ? ` for ${j.title} at ${j.company}` : ""}. Read the job, relevant career evidence, approved claims, selected template/assets, general instructions and template notes from Openings. Use a frozen application context. Write the CV, letter and form answers from supported facts. Compile externally, inspect the result and upload PDF plus filled sources as a new draft. Do not mark the application sent.`;
      showModal(
        `<h2>A brief for your agent.</h2><p>The companion skill supplies this workflow; MCP provides the actual data and operations.</p><textarea id="agent-brief" rows="10" aria-label="Agent brief">${esc(brief)}</textarea><div class="actions"><button class="btn" onclick="UI.close()">Close</button><button class="btn primary" onclick="UI.copy(document.getElementById('agent-brief').value)">${ico("copy")} Copy brief</button></div>`,
      );
    },
    copy(text) {
      if (navigator.clipboard && window.isSecureContext)
        navigator.clipboard
          .writeText(text)
          .then(() => toast("Copied."))
          .catch(() => toast("Copy is unavailable in this browser."));
      else {
        let t = document.createElement("textarea");
        t.value = text;
        document.body.appendChild(t);
        t.select();
        document.execCommand("copy");
        t.remove();
        toast("Copied.");
      }
    },
  };
  window.UI = UI;
  window.addEventListener("hashchange", () => {
    route = location.hash.slice(1) || "overview";
    if (!navs.some((n) => n[0] === route)) route = "overview";
    close();
    render();
    window.scrollTo(0, 0);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      close();
      UI.menu(false);
    }
    if (e.key === "Tab" && $("#overlay").children.length) {
      let targets = [
          ...$("#overlay").querySelectorAll(
            'button,a[href],input,select,textarea,[tabindex="0"]',
          ),
        ].filter((el) => !el.disabled && el.offsetParent !== null),
        first = targets[0],
        last = targets.at(-1);
      if (e.shiftKey && document.activeElement === first) {
        last?.focus();
        e.preventDefault();
      }
      if (!e.shiftKey && document.activeElement === last) {
        first?.focus();
        e.preventDefault();
      }
    }
  });
  render();
})();
