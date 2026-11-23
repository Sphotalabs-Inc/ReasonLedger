/* ReasonLedger UI — find a decision: browse by area, search, and ask "why this code?".
 *
 * Live mode only. Decisions are grouped by where in the repo their `justifies` anchors
 * point, so a reader can start from a part of the system instead of a file path they
 * would have to know. Everything shown here comes from the view already loaded, except
 * Why, which asks the server because it resolves a line to a symbol.
 */
(function (global) {
  const R = global.RLRender;
  const Refs = global.RLRefs;
  const esc = R.escapeHtml;

  /** Directory levels that make up an area: deep enough to separate services from routes. */
  const AREA_DEPTH = 3;
  const ROOT_AREA = "(repo root)";
  const UNANCHORED = "(not anchored to any code)";

  /** What an anchor's precision means to a reader. Ordered most to least precise. */
  const MATCH_ORDER = { symbol: 0, line: 1, file: 2 };
  const MATCH_LABELS = {
    symbol: {
      text: "exact symbol",
      hint: "Anchored to the function or class that contains this line",
    },
    line: { text: "line range", hint: "Anchored to a line range that covers this line" },
    file: {
      text: "whole file only",
      hint: "Anchored to the file, not to these lines — it may not speak to this exact code",
    },
  };
  const LOCUS_KINDS = { symbol: "symbol", lines: "line range", file: "whole file" };

  let query = "";
  let whyValue = "";
  let whyHtml = "";
  /** How many decisions the ledger holds, so an empty ledger reads differently from an uncovered file. */
  let ledgerSize = 0;
  /** Set by mount: the one authenticated request app.js owns (see api.js). */
  let apiRequest = null;
  /** Decision id → the decisions it replaced, nearest first; built from every record, not just those shown. */
  let replaced = {};
  /** Set by mount: opens the review dialog (approve or retire) for a decision found here. */
  let openReview = null;

  function locusFile(locus) {
    const symbolAt = locus.indexOf("::");
    if (symbolAt >= 0) return locus.slice(0, symbolAt);
    const ranged = /^(.*):\d+(-\d+)?$/.exec(locus);
    return ranged ? ranged[1] : locus;
  }

  function locusKind(locus) {
    if (locus.indexOf("::") >= 0) return "symbol";
    return /:\d+(-\d+)?$/.test(locus) ? "lines" : "file";
  }

  /** The Why query that asks about exactly this anchor (Why takes one line, not a range). */
  function whyTargetFor(locus) {
    const ranged = /^(.*):(\d+)(-\d+)?$/.exec(locus);
    return ranged && locus.indexOf("::") < 0 ? ranged[1] + ":" + ranged[2] : locus;
  }

  function areaOf(file) {
    const dirs = file.split("/").slice(0, -1).slice(0, AREA_DEPTH);
    return dirs.length ? dirs.join("/") : ROOT_AREA;
  }

  function unique(items) {
    return items.filter(function (item, index) {
      return items.indexOf(item) === index;
    });
  }

  function lociHtml(loci) {
    if (!loci.length) return "";
    return (
      '<ul class="loci">' +
      loci
        .map(function (locus) {
          const kind = locusKind(locus);
          return (
            '<li class="locus locus-' +
            kind +
            '"><button type="button" class="locus-link" data-why="' +
            esc(whyTargetFor(locus)) +
            '" title="Ask why about this code">' +
            esc(locus) +
            '</button> <span class="locus-kind">' +
            esc(LOCUS_KINDS[kind]) +
            "</span></li>"
          );
        })
        .join("") +
      "</ul>"
    );
  }

  function searchText(d) {
    return [d.id, d.context, d.choice]
      .concat(d.justifies || [], d.assumptions || [], d.alternatives_rejected || [])
      .join(" ")
      .toLowerCase();
  }

  /** Every word typed must appear somewhere in the decision, in any order. */
  function matchesQuery(d, text) {
    const words = text.toLowerCase().split(/\s+/).filter(Boolean);
    const haystack = searchText(d);
    return words.every(function (word) {
      return haystack.indexOf(word) >= 0;
    });
  }

  function bucket(groups, label, d) {
    if (!groups[label]) groups[label] = [];
    groups[label].push(d);
  }

  function sortedGroups(groups) {
    return Object.keys(groups)
      .sort()
      .map(function (label) {
        return { label: label, items: groups[label] };
      });
  }

  /** The folders a decision's code anchors sit in; it shows under every folder it touches. */
  function groupDecisions(decisions) {
    const byFolder = {};
    decisions.forEach(function (d) {
      const files = unique((d.justifies || []).map(locusFile));
      (files.length ? unique(files.map(areaOf)) : [UNANCHORED]).forEach(function (area) {
        bucket(byFolder, area, d);
      });
    });
    return sortedGroups(byFolder);
  }

  function indexReplaced(all) {
    replaced = {};
    all.forEach(function (d) {
      if (d.status === "superseded" && d.superseded_by) {
        (replaced[d.superseded_by] = replaced[d.superseded_by] || []).push(d);
      }
    });
  }

  /** What this decision replaced, and what that replaced in turn; `seen` stops a cycle. */
  function replacedChain(id, seen) {
    return (replaced[id] || []).reduce(function (chain, old) {
      if (seen[old.id]) return chain;
      seen[old.id] = true;
      return chain.concat([old], replacedChain(old.id, seen));
    }, []);
  }

  /** The decisions behind this one, folded away: the card stays one decision, the history one click off. */
  function replacedHtml(d) {
    const chain = replacedChain(d.id, {});
    if (!chain.length) return "";
    return (
      '<details class="item-details replaced"><summary>Replaces ' +
      esc(chain.length) +
      (chain.length === 1 ? " earlier decision" : " earlier decisions") +
      "</summary><ul class=\"item-notes\">" +
      chain
        .map(function (old) {
          return (
            "<li><code>" + esc(old.id) + "</code> " + esc(old.choice || old.context || "") +
            (old.superseded_reason ? " <em>Replaced because: " + esc(old.superseded_reason) + "</em>" : "") +
            "</li>"
          );
        })
        .join("") +
      "</ul></details>"
    );
  }

  /** A decision led by the question it answered; the id is reference, not the headline. */
  function decisionCard(d, loci, badgeHtml) {
    return (
      '<article class="item browse-item status-' +
      esc(d.status) +
      '"><p class="item-title" title="Click to expand or collapse">' +
      esc(d.context || "(no context recorded)") +
      "</p>" +
      '<p class="item-body">' +
      esc(d.choice || "") +
      "</p>" +
      lociHtml(loci) +
      Refs.html(d) +
      R.reasoningDetails(d) +
      replacedHtml(d) +
      '<p class="item-meta"><code>' +
      esc(d.id) +
      "</code>" +
      ' <span class="badge">' +
      esc(d.status) +
      "</span>" +
      (badgeHtml || "") +
      R.proposerBadge(d) +
      R.pendingBadge(d) +
      "</p>" +
      global.RLProvenance.html(d) +
      global.RLReview.findAction(d) +
      "</article>"
    );
  }

  function areaBrowserHtml(decisions, text) {
    const shown = text.trim()
      ? decisions.filter(function (d) {
          return matchesQuery(d, text);
        })
      : decisions;
    if (!shown.length) {
      return '<p class="hint">No decision matches “' + esc(text.trim()) + "”.</p>";
    }
    // A search for an id leads with that decision; the rest only mention it and say so.
    const askedIds = Refs.asked(shown, text);
    const direct = shown.filter(function (d) {
      return askedIds.indexOf(d.id) >= 0;
    });
    const rest = shown.filter(function (d) {
      return askedIds.indexOf(d.id) < 0;
    });
    const groups = groupDecisions(rest);
    const searching = Boolean(text.trim());
    const hint =
      "Grouped by the folder each decision's code is in, so one whose code is in two folders " +
      'shows under both. The <a href="#" data-open-tab="map">Map tab</a> groups them by module.';
    const mentions = direct.length ? " that " + (rest.length === 1 ? "mentions" : "mention") + " it" : "";
    const counted = rest.length
      ? '<p class="hint">' +
        esc(rest.length) +
        (rest.length === 1 ? " decision" : " decisions") +
        mentions +
        ", in " +
        esc(groups.length) +
        (groups.length === 1 ? " folder. " : " folders. ") +
        hint +
        "</p>"
      : "";
    return (
      direct
        .map(function (d) {
          return decisionCard(d, d.justifies || [], Refs.hitBadge(d, askedIds));
        })
        .join("") +
      counted +
      groups
        .map(function (group) {
          const label = esc(group.label);
          return (
            '<details class="section area"' +
            (searching || groups.length === 1 ? " open" : "") +
            '><summary><span class="section-title">' +
            "<code>" + label + "</code>" +
            '</span> <span class="section-count">(' +
            esc(group.items.length) +
            ")</span></summary>" +
            group.items
              .map(function (d) {
                return decisionCard(d, d.justifies || [], Refs.hitBadge(d, askedIds));
              })
              .join("") +
            "</details>"
          );
        })
        .join("")
    );
  }

  function whyHitHtml(d) {
    const label = MATCH_LABELS[d.match] || MATCH_LABELS.file;
    const superseded = d.status === "superseded";
    const note = superseded
      ? '<p class="item-supersede">Superseded' +
        (d.superseded_by ? " by " + esc(d.superseded_by) : "") +
        " — read the successor for current guidance.</p>"
      : "";
    const badge =
      ' <span class="badge match-badge match-' +
      esc(d.match) +
      '" title="' +
      esc(label.hint) +
      '">' +
      esc(label.text) +
      "</span>";
    return decisionCard(d, d.matched_loci || [], badge).replace("</article>", note + "</article>");
  }

  /** One anchored decision in a near-miss list: where it sits, what it chose, how to hit it. */
  function nearbyItemHtml(entry) {
    return (
      '<li class="why-nearby-item"><code>' +
      esc(entry.id) +
      "</code> <code>" +
      esc(entry.locus) +
      '</code> <span class="badge">' +
      esc(entry.status) +
      "</span><br />" +
      esc(entry.choice) +
      '<br /><span class="hint">Try <code>' +
      esc(entry.command) +
      "</code></span></li>"
    );
  }

  function ledgerSizeText(size) {
    if (!size) return "the ledger is empty.";
    return "the ledger holds " + size + (size === 1 ? " decision." : " decisions.");
  }

  /** A miss is never "nothing here" when the file has decisions anchored elsewhere (S59.4). */
  function whyMissHtml(data, size) {
    const where = data.target.split(":")[0];
    if (!data.path_exists) {
      return (
        '<p class="error">There is no file at <code>' +
        esc(where) +
        "</code> in this repo. Use a path relative to the repo root, " +
        "like <code>src/app.py</code>.</p>"
      );
    }
    const entries = data.nearby || [];
    if (!entries.length) {
      return (
        '<p class="hint">No decision names this file (<code>' +
        esc(where) +
        "</code>); " +
        esc(ledgerSizeText(size)) +
        "</p>"
      );
    }
    const live = entries.filter(function (e) {
      return e.status === "active" || e.status === "stale";
    });
    const counts = {};
    entries.forEach(function (e) {
      if (live.indexOf(e) < 0) counts[e.status] = (counts[e.status] || 0) + 1;
    });
    const notes = Object.keys(counts).map(function (status) {
      return counts[status] + " " + status;
    });
    const asked = /:(\d+)$/.exec(data.target);
    return (
      '<p class="hint">No decision covers ' +
      (asked ? "line " + esc(asked[1]) : "this place") +
      " of <code>" +
      esc(where) +
      "</code>, but this file has:</p>" +
      '<ul class="why-nearby">' +
      live.map(nearbyItemHtml).join("") +
      "</ul>" +
      (notes.length ? '<p class="hint">and ' + esc(notes.join(", ")) + " (not listed)</p>" : "")
    );
  }

  function whyResultsHtml(data, size) {
    if (!data.count) return whyMissHtml(data, size === undefined ? ledgerSize : size);
    const hits = data.decisions.slice().sort(function (a, b) {
      return (MATCH_ORDER[a.match] || 0) - (MATCH_ORDER[b.match] || 0);
    });
    const coarseOnly = hits.every(function (d) {
      return d.match === "file";
    });
    const caveat = coarseOnly
      ? '<p class="hint">These decisions are anchored to the whole file, not to this ' +
        "line, so they describe the file rather than this exact code.</p>"
      : "";
    return (
      '<p class="hint">' +
      esc(data.count) +
      (data.count === 1 ? " decision" : " decisions") +
      " for <code>" +
      esc(data.target) +
      "</code>, most precise first.</p>" +
      caveat +
      hits.map(whyHitHtml).join("")
    );
  }

  function filesIn(decisions) {
    const files = [];
    decisions.forEach(function (d) {
      (d.justifies || []).forEach(function (locus) {
        files.push(locusFile(locus));
      });
    });
    return unique(files).sort();
  }

  function shellHtml(decisions) {
    return (
      '<section class="why-card" id="section-find"><h2 class="why-card-title">' +
      "Find a decision</h2>" +
      '<p class="hint">Search, or open a function to see what was ' +
      "decided there and which code it covers.</p>" +
      '<input type="search" id="browse-search" class="search-input" ' +
      'placeholder="e.g. promo, consent, subscription_service" ' +
      'aria-label="Search decisions" value="' +
      esc(query) +
      '" />' +
      '<div id="browse-results">' +
      areaBrowserHtml(decisions, query) +
      "</div></section>" +
      '<section class="why-card" id="section-why"><h2 class="why-card-title">' +
      "Why does this code look like this?</h2>" +
      '<p class="hint">Enter a file, optionally with <code>:line</code> or ' +
      "<code>::function</code>. Suggestions list files that decisions point at.</p>" +
      '<form class="why-form" id="why-form">' +
      '<input name="target" list="why-files" autocomplete="off" ' +
      'placeholder="e.g. backend/app/services/subscription_service.py:300" ' +
      'aria-label="File, line or symbol" value="' +
      esc(whyValue) +
      '" /><datalist id="why-files">' +
      filesIn(decisions)
        .map(function (file) {
          return '<option value="' + esc(file) + '"></option>';
        })
        .join("") +
      '</datalist><button type="submit" class="primary">Ask</button></form>' +
      '<div id="why-results">' +
      whyHtml +
      "</div></section>"
    );
  }

  async function askWhy(target) {
    const out = document.getElementById("why-results");
    if (!out) return;
    whyValue = target;
    if (!target) {
      whyHtml = '<p class="error">Enter a file path, like src/app.py.</p>';
    } else {
      try {
        const data = await apiRequest("/api/why?target=" + encodeURIComponent(target));
        whyHtml = whyResultsHtml(data);
      } catch (err) {
        whyHtml = '<p class="error">' + esc(err.message || err) + "</p>";
      }
    }
    out.innerHTML = whyHtml;
  }

  /** `all` is every record: what a shown decision replaced is found there even when not listed. */
  function mount(view, request, onReview, all) {
    apiRequest = request;
    openReview = onReview;
    const host = document.getElementById("browse-root");
    if (!host) return;
    const decisions = view.decisions || [];
    Refs.index(decisions);
    indexReplaced(all || decisions);
    ledgerSize = (all || decisions).length;
    host.innerHTML = shellHtml(decisions);
    const results = document.getElementById("browse-results");
    const search = document.getElementById("browse-search");
    function find(text) {
      query = text;
      results.innerHTML = areaBrowserHtml(decisions, query);
    }
    search.addEventListener("input", function (ev) {
      find(ev.currentTarget.value);
    });
    document.getElementById("why-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      askWhy((ev.currentTarget.elements.target.value || "").trim());
    });
    host.addEventListener("click", function (ev) {
      const review = ev.target.closest("[data-review-id]");
      if (review) return openReview(review.getAttribute("data-review-id"), review.getAttribute("data-review-kind"));
      const ref = ev.target.closest("[data-find]");
      if (ref) {
        search.value = ref.getAttribute("data-find");
        find(search.value);
        search.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      const title = ev.target.closest(".browse-item .item-title");
      if (title) title.classList.toggle("expanded");
      const link = ev.target.closest("[data-why]");
      if (!link) return;
      const form = document.getElementById("why-form");
      form.elements.target.value = link.getAttribute("data-why");
      form.scrollIntoView({ behavior: "smooth", block: "center" });
      askWhy(form.elements.target.value);
    });
  }

  global.RLBrowse = {
    mount: mount,
    ask: askWhy,
    setQuery: function (text) {
      query = text;
    },
    locusFile: locusFile,
    areaOf: areaOf,
    groupDecisions: groupDecisions,
    matchesQuery: matchesQuery,
    whyResultsHtml: whyResultsHtml,
  };
})(window);
