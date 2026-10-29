---
name: citation-consistency
description: Use this skill to check a document's citations against its own reference list, without looking anything up outside the document. Finds every in-text and note citation, checks that each one resolves to an entry in the References or Bibliography, that a References list holds only cited works, that citations follow the house citation style (with a proposed fix for each malformed one), and that the document uses one citation system throughout. Invoke when asked to check citations, in-text citations, footnote citations, or whether the citations and the reference list match.
metadata:
  draft_detective:
    title: Citations & Reference List
    description: Do your citations and your reference list agree? Checks that every citation resolves to a reference entry, that a References list holds only cited works, and that citations are formatted consistently, with a proposed fix for each malformed one. Works from the document alone, with no web access.
    category: citation_check
    experimental: false
    icon: quote
    propose_edits: true
---

# Citations & Reference List

You are a specialist document reviewer. Check that the document's citations and its reference list agree with each other and follow the house citation style below. Everything you need is in the document: do not look anything up, and do not judge whether a cited source exists or supports the claim. Read or search the document's content as needed.

Report problems; do not rewrite the document. Where the fix for a malformed citation is fully determined, attach it as a proposed edit the author can accept or reject.

## Terms

- A **citation** points the reader to a source: *(Marr, 1991)* in the text, *Woodward (1991)* worked into a sentence, a footnote or endnote that names a source, or a source line under a figure or table (*SOURCE: Marr, 1991.*).
- A **note** is a footnote or an endnote. The text carries a **callout**, a superscript number; the note itself sits at the foot of the page, at the end of a section, or at the end of the document under a *Notes* heading. In a text rendering of a document, callouts may appear as `[^3]`, as a bracketed number linking to a footnotes or endnotes section, or as a plain number after punctuation, and the notes as a numbered list near the end. Follow each callout to its note.
- The **reference list** is the alphabetized list of full entries, usually at the end of the document. Its heading tells you what kind of list it is:
  - **References** (or *References Cited*, *Works Cited*): the works cited, and only those. Every entry should be cited somewhere.
  - **Bibliography** (or *Works Consulted*, *Selected Bibliography*, *References Reviewed*, *Further Reading*): the works cited plus works consulted. Entries that are never cited are fine.

## The house citation style

A document uses exactly one of three citation systems, consistently.

1. **Author–date.** The citation is the author's surname and the year, in parentheses in the text or in a figure or table note: *(Marr, 1991)*. A citation inside a footnote or endnote is worded as in the text: in parentheses after the note's own words (*…as several programs found (Marr, 1991).*) or worked into a pointer (*See Marr (1991).*). A note holding only a bare short form (*Marr, 1991.*, *see Marr, 1991.*) belongs to the full-footnote system, not this one.
2. **Author–title.** The citation sits in a note and gives the author's surname and the main title (no subtitle): *Gibbon and Mueller, The Decline and Fall of the Roman Empire.* Up to three surnames, otherwise the first and *et al.*
3. **Full footnote with short forms.** The first citation of a source is a footnote holding the full entry, with the first author's name in normal order (*Ken Smith, Junk English, Blast Books, 2001.*); every later citation of it is a footnote with the author–date short form, without parentheses (*Smith, 2001.*). The short form names the authors exactly as an author–date citation in the text would (both names for two authors, all three for three, the first and *et al.* for four or more) and may carry a page (*Solberg and Lund, 2019, p. 140.*). It is never author–title.

Whichever system the document uses, the full entry for every cited source must also appear in a References or Bibliography list. Notes alone are not enough, even in a short document.

Author–date citations, in text or as short forms in notes, take these forms:

- **Comma between author and year:** *(Marr, 1991)*, not *(Marr 1991)*.
- **Author worked into the sentence:** the year in parentheses straight after the name, and the name not repeated: *Woodward (1991) reported…*, *Howard (1983, p. 12) puts it…*. Not *Woodward (Woodward, 1991)* or *Woodward, (1991)*.
- **Two authors:** *and*, never *&*: *(Cabot and Dickens, 1995)*.
- **Three authors:** all three names, serial comma: *(Cabot, Dickens, and Murphy, 1998)*. No *et al.* for three or fewer authors.
- **Four or more authors:** the first author and *et al.*, no comma before *et al.*, and *al.* with its period: *(Marquis et al., 2020)*. When the same first author leads two different groups with the same year, add the second name: *(Kakalik, Ebener, et al., 2021)*.
- **Pages and parts:** *p.* for one page, *pp.* for a range with an en dash, after a comma: *(Dickens, 1993, p. 23)*, *(Dickens, 1993, pp. 43–45)*. Also *(Dickens, 1993, Appendix D)*, *(Dickens, 1993, Figure 4.1)*. No comma inside a page number of four or more digits. A direct quotation carries its page number when the source has pages.
- **Several sources:** separated by semicolons, never *and*, in one consistent order: *(Cabot, 2002; Dickens, 1998)*.
- **Same author, same year:** a lowercase letter after the year, matching the entry: *(Davis and Saum-Manning, 2018a)*. Undated works: *(FBI, undated-a)*.
- **Same surname, same year, different people:** initials or given names to tell them apart: *(P. Hyde, 1997; L. Hyde, 1997)*.
- **Refinements:** *see*, *see also*, *as quoted in*, *as reported in* and *data from* are allowed inside the parentheses. *cf.* is not.
- **Placement:** normally at the end of the sentence, before the period; after the period only at the end of a block quotation.

Forms the style does not allow:

- ***ibid.*, *ibid*, *op. cit.*, *id.*, *loc. cit.***, in text or notes. Each must become the citation it stands for.
- **Numbered citations** pointing into a numbered reference list: *[3]*, *[3, 5–7]*.
- **A URL or hyperlink standing in for a citation.** URLs belong only in the reference list.

## What is not a problem

- **Interviews and personal communications** conducted by the authors (*a U.S. Department of State official, interview with the authors, June 4, 2016*) appear only in notes and never in the reference list. Do not report them as missing from the list or as full citations without short forms.
- **Substantive notes** that comment rather than cite. A note can hold both; check only its citations.
- **Mentions that are not citations:** a person named as a subject (*Marr argued in a 1991 interview…* with no source pointed to), the names of laws, programs or datasets used as names, years in ordinary prose, and the document's own cross-references (*see Chapter 3*, *Table 2.1*).
- **Citations inside quoted material** that reproduce a source's own citation.
- **Material outside the body:** the reference list's own entries (except as targets to match), the table of contents, abbreviation lists, author biographies, and cover or boilerplate text.
- **The format of the reference list entries themselves.** This check matches citations to entries; it does not restyle entries.
- **Uncited entries in a Bibliography**, or in a list whose heading or a note under it says it includes works consulted but not cited.

## Procedure

1. **Read the whole document first.** Find the reference list and note its heading and any note under it. Find the notes, if any. Note how many lines the document has, as your tools report it: if it has more than 300 lines and you can hand work to sub-agents, follow **Long documents** below for step 3.
2. **Index the reference list.** For each entry, record its line, its author or authoring organization (surnames in order), its year or *undated*, any year letter, and its main title. Note entries that share a surname or a year, since citations to them must be told apart.
3. **Find every citation** in the body, the notes, and figure and table source lines. For each, record its line, its exact text, the system it uses, and the entry it points to. Read every sentence: parenthetical citations hide in long sentences and grouped citations hold several sources. Resolve each note callout to its note and read the note's citations. Track the first full-footnote citation of each source, so later ones can be expected to use the short form.
4. **Decide the document's citation system** from what most citations use. If more than a few citations use another system, the document mixes systems.
5. **Match each citation to an entry.** What must agree depends on the system. An author–date citation, and a short form in the full-footnote system, matches when the first author's surname (or organization), the year and any year letter agree, and its other names agree with the entry's. An author–title citation carries no year: it matches when its surnames (or organization) and its main title agree with the entry's, ignoring the subtitle; a citation with no author matches on the title alone. A full first footnote matches on its authors, title and year. Then sort out the rest in this order, reading "year" as "main title" for author–title citations:
   - **Ambiguous:** it fits more than one entry, most often a bare year where the list has *2022a* and *2022b* by the same authors, or one surname shared by two authors in the same year. Never settle it by picking one entry yourself, even when one seems likelier or another citation already points to the other: report it as ambiguous. It is not a mismatch, and it gets no edit.
   - **Format:** it points to exactly one entry, but names its authors in the wrong form for the entry's author count (*et al.* for three or fewer authors, the first name alone for two or three, every name for four or more). That is a format problem, not a mismatch.
   - **Mismatch:** no entry fits, but one is a near miss that differs in exactly one thing: the same surnames with another year, a spelling variant of the same surname (a letter or two apart, *Halvorsen* for *Halverson*) with the same year, a year letter the entry does not carry or a different letter, or a second author who differs. A different surname with a different year is not a near miss. A near miss is a mismatch, not a missing entry.
   - **Missing:** no entry fits and none is a near miss.
6. **Check each citation's form** against the house style for its system, and work out the corrected citation when the fix is fully determined by the citation and its entry.
7. **If the list is headed References** and neither its heading nor a note under it says it includes uncited works, go through the list entry by entry and decide whether any citation points to it, searching the document for the entry's first surname when you have not already matched it. Count as cited a source cited only through a full-footnote citation, every entry an ambiguous citation could mean, and the entry a mismatched citation most likely means: those problems are already reported, and the author may have meant that entry. Report the rest as uncited.
8. **Check your findings before reporting.** Re-read each flagged citation in place: is it really a citation, is it really absent from the list (search the list for the surname, since the entry may be sorted under an organization or a second spelling), and is the corrected form right? Drop anything that fails.

## Long documents

When the document has more than 300 lines and you can hand work to sub-agents, split the search for citations (step 3); keep the reference list index, matching and the uncited check yourself, because they need the whole document.

1. **Read the whole document** and index the reference list (steps 1 and 2).
2. **Cut the body into consecutive parts** at chapter or major-section headings, each roughly 100 to 250 lines, and no more than eight parts. Notes at the end of the document go with the part that calls them out, or form their own part.
3. **Give each part to its own sub-agent**, all at once if you can. Tell each one the first and last line it owns, the line range of the reference list, and the citation system you expect, and ask it to follow this skill's steps 3, 5, 6 and 8 for its range only, to report its own issues in the usual format with the usual edit rules except citations with no entry (a source missing from the list may be cited in several parts, and it gets one issue for the whole document), not to write the report deliverable, and to reply with every citation it found and the first and last line it reviewed. For each citation the reply gives its line, its text, and the entry it matched; for an ambiguous citation, every entry it could mean; for a mismatch, the entry it most likely means; otherwise *none*. The uncited check in step 5 needs those entries.
4. **Check that every part came back.** If a sub-agent failed, or reviewed less than its range, review the missing lines yourself.
5. **Do the document-wide checks yourself** from the sub-agents' replies: citations with no entry (one issue per source across all parts, anchored on its first citation in the document), the mixed-system check, the uncited-entry check, and whether the list is missing. Report only those issues: the sub-agents have already reported every other citation-level issue in their parts, so never report one of those again, even to restate it.

## Reporting

Report issues following the conventions defined in the `issues` skill. Do not emit issues for citations that pass. Anchor every issue on the line of the citation or entry it concerns, and quote the citation exactly in the description.

- **Citation with no entry** → title `"Citation Not in Reference List: [citation]"`, **severity: high**. One issue per source, anchored on its first citation; list the lines of any others in the description.
- **Citation that nearly matches an entry** (wrong year, misspelled surname, a year letter the entry lacks or a different one, a different second author) → title `"Citation Does Not Match Reference: [citation]"`, **severity: medium**. Name the entry it most likely means, quote that entry's author and year, and say what differs. Say that the entry may be the one in error.
- **Citation that fits more than one entry** → title `"Ambiguous Citation: [citation]"`, **severity: medium**. Name the entries it could mean and say what would tell them apart (a year letter, a second name, initials).
- **Uncited entry in a References list** → title `"Uncited Reference: [first author, year]"`, **severity: low**. One issue per entry, anchored on the entry. Suggest citing it or moving it to a Bibliography.
- **No reference list** although the document cites sources → title `"Missing Reference List"`, **severity: high**, anchored on the first citation.
- **Malformed citation** → title `"Citation Format: [citation]"`, **severity: low**. Say which rule it breaks and give the corrected citation.
- ***ibid.*, *op. cit.* and similar** → title `"Ibid. or Op. Cit. Citation"`, **severity: low**. Name the source it stands for, if the preceding citation makes that clear, and give the short form that replaces it.
- **Numbered citation, URL used as a citation, or *cf.*** → title `"Citation Form Not Allowed: [citation]"`, **severity: low**. Say what form the citation should take; propose no edit, since the author must supply the source's author and year or reword the pointer.
- **Two citation systems in one document** → title `"Mixed Citation Systems"`, **severity: medium**, anchored on the first citation in the minority system. Name both systems, give the lines of a few examples of each, and say which system the document mostly uses.

### Proposed edits

When you can attach proposed edits, attach one to a **Citation Format** issue, an **Ibid. or Op. Cit.** issue, or a **Citation Does Not Match Reference** issue whose fix is fully determined:

- **Format:** the corrected form follows from the citation and its entry alone (*(Marr 1991)* → *(Marr, 1991)*; *(Cabot et al., 1995)* for a two-author entry → *(Cabot and Dickens, 1995)*; *Woodward (Woodward, 1991)* → *Woodward (1991)*).
- **Ibid.:** in the full-footnote system, when the preceding citation names exactly one source, the replacement is its short form with any page number the ibid. carried (*Ibid., p. 48.* → *Warner, 1992, p. 48.*). In the other systems the wording of the replacement note is the author's choice, so name the source and propose no edit.
- **Mismatch:** exactly one entry is a near match, and the difference is the year, a year letter the entry carries differently, or a surname spelling. Make the citation agree with the entry.

Quote the citation verbatim as the text to replace, with only as much surrounding text as makes it unique in its paragraph, and give the replacement. Keep every page number, refinement (*see*, *as quoted in*) and footnote callout. A citation missing from the list, an ambiguous citation, an uncited entry, a disallowed form other than ibid., and mixed systems get no edit: they need the author's decision. Never propose an edit that guesses.

### Volume

Report every citation with no entry, every mismatch and every ambiguous citation. Report format problems one issue per citation up to 40; if there are more, report the rest one issue per rule broken, titled `"Citation Format: [rule]"`, listing each citation's line and its corrected form, with an edit for each.

## Report

In the report deliverable, state the citation system the document uses, the reference list's heading and whether uncited entries were checked, how many citations you found and how many resolved to an entry, and the count of each kind of issue. Keep it short.
