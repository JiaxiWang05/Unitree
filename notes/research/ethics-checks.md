# Ethics and data-protection checks: G1 humanoid robot stand at a Durham Open Day

Prepared for a Durham University PhD student (Computer Science / Engineering). Sources were checked between 29 October and 4 November 2026. Every factual claim has its URL next to it. Where I could not open a page, I say why (for example, a Durham SSO login or a 403 error). This is research and compliance support, not legal advice. The Durham Information Governance Unit / DPO and the department ethics committee decide.

**Study as described:** a Unitree G1 humanoid with locomotion disabled stands at an Open Day stand. A webcam does person tracking from pose keypoints, with no face recognition and no identification. The robot invites passers-by who are wearing green and chats with them by voice for about 1 minute. Voice audio and occasional camera frames are streamed to the OpenAI Realtime API (gpt-realtime, a US company). The robot's own disk currently stores, for each visit, audio (mic and robot), a camera frame every 2 s, transcripts and a 5 Hz track log. Each visitor gets a randomised opener condition, and a short questionnaire is optional. Many visitors are aged 16–17, plus parents.

---

## 0. Key findings (read first)

1. **Who reviews it:** Review happens in the **department** (Computer Science, or Engineering if that is your home department), through Durham's online **Ethics and Research Integrity Portal**. Departments report to the relevant **faculty** ethics committee, and faculties report to the University Ethics Committee. Both CS and Engineering sit in the Faculty of Science. The portal and the detailed review guides are behind Durham SSO. No turnaround time is published.
2. **Under-18s:** Durham's public policy treats children/minors as a "potentially vulnerable" group. It requires safeguarding arrangements, which "may include" a DBS check. Durham's 2025 Safeguarding Policy says to get written consent (from a parent or guardian for a child) before photos or video/audio recordings, "where appropriate". Durham defines children as under 18. I found **no public Durham rule** on whether 16–17-year-olds can consent alone. That guidance is in the internal Ethics & Governance toolkit. The ICO says UK GDPR sets no general minimum age outside online services, so a Gillick-style competence test applies.
3. **OpenAI's contract is stricter than UK law on minors.** The OpenAI Services Agreement (effective 1 Jan 2026), clause 3.3(c), says the customer will not "allow minors to use OpenAI Services without consent from their parent or guardian". OpenAI's API Under-18 guidance treats minors as under 18. It also says not to process personal data of children under 13 (or under the applicable age of digital consent) without first enabling **Zero Data Retention**. **Practical consequence:** a 16–17-year-old who talks to the robot needs **parent/guardian consent** before any audio goes to OpenAI, even if they are competent to consent to the research itself.
4. **OpenAI data handling (Realtime API):** By default, API data is **not used for training**. Abuse-monitoring logs are kept for **up to 30 days**. `/v1/realtime` keeps no application state and **is eligible for Zero Data Retention**, but ZDR needs OpenAI's approval through sales. EU data residency (`eu.api.openai.com`) supports `/v1/realtime` for both storage and processing, and requires ZDR/MAM. The **UK region (`gb.api.openai.com`) does not list `/v1/realtime`** and has no UK regional processing. With the default setup, UK data is processed by **OpenAI OpCo, LLC (US)** under the **EU SCCs plus the ICO UK Addendum**. OpenAI is **not** on the Data Privacy Framework list: searching "OpenAI" on 3 Nov 2026 returned no results. The UK–US "data bridge" therefore cannot be relied on, and you need a **transfer risk assessment**.
5. **Biometrics:** Under ICO guidance, images and voice are **special category biometric data only if you use them to uniquely identify someone**. Pose keypoints with no identification are personal data, not special category biometric data. You still need to document this reasoning in the DPIA.
6. **A DPIA is effectively required.** The ICO says a DPIA is required for surveillance systems in most cases. Its high-risk list requires one for "innovative technology (including AI)" combined with any other criterion, and you have several: tracking behaviour, vulnerable data subjects (children), and monitoring of a publicly accessible area. Durham's policy says identifiable personal data "may require" a DPIA, and the Information Governance Unit reviews DPIAs.
7. **Audio is the highest-risk element.** The ICO calls recording conversations between members of the public "highly intrusive". Audio should be off by default, and you should take extra steps to make clear that audio is being recorded. Signs must be visible **before** people enter the camera's field of view. A website notice alone is not enough.
8. **Retention:** Durham's default for source research data is **10 years** after publication or the end of the project. The policy allows a different period where an ethical consideration requires it. Use this to justify deleting raw audio and video early and keeping only derived, anonymised data for 10 years.

---

## 1. Durham University process and policy

### 1.1 Which committee, which system, how long

- **Ethics review goes through the Ethics and Research Integrity Portal.** The Research Integrity Policy and Code of Good Practice, s.7.5, says: "Ethics review and an initial check of governance requirements is undertaken via the University's Ethics and Research Integrity Portal". Portal: https://forms.ethics.durham.ac.uk/ActivityForm/Index (**behind Durham Microsoft SSO login**). Policy, approved by Senate on 4 February 2025: https://www.durham.ac.uk/research/ethics--governance/research-integrity-policy-and-code-of-good-practice/
- **Review must happen before any work starts.** Section 7.3: "All projects must identify relevant ethical considerations and, where appropriate, undergo full ethical review (and secure favourable opinions) before any work starts". Section 7.4 says significant amendments may need re-approval. Same URL as above.
- **Human participants and personal data always need review** (s.7.7.1). The exemptions in s.7.7.1.2 do not apply here: the study is research, it involves vulnerable groups, and it includes automated processing. Same URL.
- **Devolved structure:** "Practical review of applications for (non-animal / non-NHS) projects devolved to departments. Departments provide assurance to the relevant faculty ethics committee ... which in turn provide assurance to Ethics Committee." Source: https://www.durham.ac.uk/research/ethics--governance/2022-research-integrity-assurance-report/
- **The portal is used in all departments.** Its first part is a checklist that signposts DPIAs, insurance, health and safety, and trusted research. Sources: https://www.durham.ac.uk/research/ethics--governance/2024-research-integrity-statement/ and https://www.durham.ac.uk/research/ethics--governance/2025-research-integrity-statement/ . The 2025 statement also says the former Ethics in Research policy was merged into the Research Integrity Policy.
- **Ethics committees exist at Department, Faculty and University level.** Source: https://www.durham.ac.uk/research/ethics--governance/ (see "Ethics Committees - Independent Members Wanted").
- **Faculty:** Computer Science and Engineering are both departments in the Faculty of Science. Source: https://www.durham.ac.uk/departments/academic/ . I took this from the search-result summary and did not open the page; see the addendum.
- **Typical review time: not published.** The documents that would state it are all on internal SharePoint, behind SSO: "roles and responsibilities of ethics committees", "ethics review processes" and the "Ethics Review Guide". The Research Integrity Policy s.3.6.5 links to:
  - https://durhamuniversity.sharepoint.com/teams/ResearchEthicsGovernance/SitePages/Operational-Guidelines-for-ethics-Sub-Committees.aspx
  - https://durhamuniversity.sharepoint.com/teams/ResearchEthicsGovernance/SitePages/Ethics-Review-Processes.aspx
  - https://durhamuniversity.sharepoint.com/teams/ResearchEthicsGovernance/SitePages/Ethics-Review-Guide.aspx
  - Ethics & Governance toolkit (internal): https://durhamuniversity.sharepoint.com/teams/ResearchEthicsGovernance
  - The old public pages (e.g. https://www.dur.ac.uk/research.innovation/governance/ethics/process/online/ and https://www.dur.ac.uk/research.innovation/governance/ethics/considerations/) now redirect to Microsoft login.
  - **Action:** ask your department ethics chair for the current turnaround, and build in time for the DPIA review by Information Governance.
- **Contacts:** For research integrity and policy, research.policy@durham.ac.uk (https://www.durham.ac.uk/research/ethics--governance/). For data protection and DPIAs, the Information Governance Unit at info.access@durham.ac.uk; one of its listed functions is to "Review data protection impact assessments" (https://www.durham.ac.uk/about-us/governance/information-governance/). For research data, research.data@durham.ac.uk (RDM Policy s.4.4, URL below).

### 1.2 Under-18s: consent, safeguarding, DBS

- **Children are a risk factor.** Research Integrity Policy s.7.8.3–7.8.4 lists "Potentially vulnerable groups, e.g. children / minors" and "Requirement for participants to take part without full knowledge and consent (e.g. involving covert observation…)" as factors that raise risk. https://www.durham.ac.uk/research/ethics--governance/research-integrity-policy-and-code-of-good-practice/
- **Safeguarding and DBS:** s.7.8.5 says: "Where activities involve children or vulnerable adults, sufficient arrangements to ensure safeguarding or participants must be put in place. This may include a requirement for researchers to complete a Disclosure and Barring Service check or equivalent." Same URL. DBS information: https://www.durham.ac.uk/about-us/safeguarding/dbs/
- **Consent:** s.7.10 says researchers must "Satisfy themselves that participants are able to give informed consent ... Where applicable, this includes provision appropriate to the needs and capacities of vulnerable individuals and groups who may require consent to be given by a gatekeeper." Same URL.
- **Durham's definition of a child:** "the definition of children includes children and young people up to the age of 18 years old". https://www.durham.ac.uk/about-us/safeguarding/safeguarding-children/
- **Recordings of children (Safeguarding Policy and Procedures 2025, Appendix A, good practice):** "Where appropriate, ensure you have written consent from the individual (or parent/guardian if a child) before taking photographs or making video/audio recordings." Also: "Always work in an open environment. If you are in a situation where you are alone with a child or an adult at risk, make sure that others can clearly observe you." The policy applies to "visitors, and members of the public who come into contact with the University and its work or events". PDF: https://www.durham.ac.uk/media/durham-university/support-services-/student-support-and-wellbeing/student-conduct/Safeguarding-Policy-and-Procedures-2025.pdf
- **Can 16–17-year-olds consent alone to low-risk research?** I found **no public Durham statement**. It is probably in the internal toolkit (SSO, see above). In UK data-protection law there is no fixed age outside online services (see 2.2). **However, OpenAI's contract requires parent/guardian consent for minors** (see 3.4), and that settles the question for the OpenAI-connected part of the interaction.

### 1.3 Research data management (RDM) policy and retention

Source for this section: https://www.durham.ac.uk/research/ethics--governance/research-data-management-policy/

- **Retention:** s.7.6.1 says: "All source Research data should be held for 10 years from the publication date of the Research results (in the case of data supporting a publication), the end of the project (in the case of funded project data) or the end of active data collection (in the case of other data)." A different period is allowed where "the data is governed by a contract or ethical consideration which stipulates a different retention period".
- **PI duties (s.5.5).** The PI is your supervisor for student research. The duties are:
  - prepare a data management plan in the University's standard format (templates in DMPonline, s.7.2.1);
  - where personal data is used, "ensure that participants are aware, at the time of consent to participate, how the data will be anonymised, used and stored including the potential for its use in future research";
  - register the data with the University wherever it is stored;
  - make the University aware of any variation from the standard retention period at deposit, and give an approved destruction date.
- **Privacy by design (s.7.3.3):** this means at minimum "(i) the informed consent of identifiable individuals over how that data will be stored, preserved and where applicable shared, and (ii) provision to store the data in a fully anonymised form".
- **Security:** s.7.3.1 says to manage data in line with the University's Information Security Policy. **Destruction:** s.7.7.1 says to destroy data in accordance with the DMP. Under s.7.7.2, "Metadata about the data asset shall include the date and reason of data deletion and shall not be deleted."

### 1.4 Data protection guidance (lawful basis, privacy notices, DPIA)

- **Lawful basis:** Durham's General Privacy Notice lists **Research** under "Public Task": "We carry out a number of tasks in the public interest including Research". For special category data: "we will usually do so on the legal basis that it is in the wider public interest (for example in relation to research)". It also says research participant data is usually anonymised as soon as possible after collection. On cloud services, it says a transfer outside the UK "may take place. In such cases appropriate protections will be in place (such as contractual arrangements…)". https://www.durham.ac.uk/about-us/governance/information-governance/privacy-notices/general-privacy-notice/
- **Privacy notice format:** Durham notices have two parts: Part 1 is the Generic Privacy Notice and Part 2 is a Tailored Privacy Notice. The researchers notice is an example: https://www.durham.ac.uk/about-us/governance/information-governance/privacy-notices/researchers/ . That page covers data about researchers, not participants, but it shows the format to copy. **I did not find a public Durham template for a research-participant privacy notice.** Ask info.access@durham.ac.uk or check the internal Ethics & Governance toolkit.
- **DPIA:** Research Integrity Policy s.7.8.6 says: "Activities involving collection or use of identifiable personal data may require a Data Protection Impact Assessment." Guidance from Information Governance is internal: https://durhamuniversity.sharepoint.com/teams/USO/SitePages/InformationGovernance.aspx (SSO). The IG Unit reviews DPIAs: https://www.durham.ac.uk/about-us/governance/information-governance/
- **Useful benchmark, Durham CCTV notice:** campus CCTV relies on legitimate interests, and "Data is stored for a maximum of 28 days." https://www.durham.ac.uk/about-us/governance/information-governance/privacy-notices/cctv/

### 1.5 Photography and filming at Open Days

- I found **no public Durham rule specific to Open Days**. The Open Days hub (https://www.durham.ac.uk/visit-us/open-days/) links only to the general privacy notices. The general notice lists "Photographing and recording events around the University" for marketing under legitimate interests, and that does **not** cover research recording.
- The rule that does apply is the Safeguarding Policy 2025 good practice on written consent before recording children (1.2 above).
- **Action:** ask the Student Recruitment / Open Day organisers whether visitors are told about filming at registration, and whether research stands need to be approved. Comparable studies used event-registration notices (see 4.2).

---

## 2. UK law and regulator (ICO) guidance

### 2.1 Lawful basis for research

- "There is no specific lawful basis for research ... you are likely to rely on either legitimate interests or public task". Also: "if you are a public authority, such as a university or an NHS organisation, public task is the most likely lawful basis." https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/the-research-provisions/principles-and-grounds-for-processing/
- **Consent to take part in research is distinct from UK GDPR consent.** The same page says: "in most cases, consent is not the most appropriate lawful basis". Consent must be withdrawable at any time "There is no exemption to this for scientific research". There is also likely to be a power imbalance for public authorities. **So:** use "public task" (Art 6(1)(e)) as the lawful basis, and keep **ethical** informed consent (or notice-and-opt-out) as a separate layer.
- **Special category data:** "There is a specific condition allowing the use of special category data or criminal offence data for research purposes, if this is in the public interest and you have appropriate safeguards in place." Same URL. This is probably not needed if you never infer special categories (see 2.4).

### 2.2 Children's data, and when 16–17-year-olds can consent

The ICO's children's guidance was updated on 15 May 2026 to reflect the Data (Use and Access) Act 2025.

- **No general minimum age.** "With the exception of organisations that offer ISS directly to children, the UK GDPR does not set a general minimum age at which a child can give their own consent. Instead, you must assess whether the child has the capacity to understand what they're agreeing to." In England this is "Gillick competence". In Scotland, children are presumed competent from 12, and "In many cases, it's reasonable to follow the Scottish approach." https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/children-and-the-uk-gdpr/how-do-the-lawful-bases-apply-to-children-s-personal-information/
- **The age of 13 applies only to online services (ISS) offered directly to children on the basis of consent.** Same URL. A robot at a physical stand is not an online service requested at a distance, so the Article 8 threshold of 13 does not apply directly. That is my own analysis; confirm it with the DPO.
- **Age-appropriate privacy information:** provide privacy information "using simple and clear language or visuals"; a DPIA is required if processing is likely to be high-risk for children; and you "must also assess any proposed use of personal information to decide whether it requires a DPIA before you begin". https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/children-and-the-uk-gdpr/what-should-our-general-approach-be-to-handling-children-s-personal-information/
- **Overview page (last updated 15 May 2026):** https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/children-and-the-uk-gdpr/

### 2.3 Video and audio recording in public spaces: signage

Source for this section: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/cctv-and-video-surveillance/guidance-on-video-surveillance-including-cctv/how-can-we-comply-with-the-data-protection-principles-when-using-surveillance-systems/ . The page itself notes that it is under review because of the DUAA.

- **DPIA:** "for the use of surveillance systems you must perform a DPIA for any type of processing that is likely to result in high risk ... This is a legal requirement and applies in most cases".
- **Signs:** "place signs prominently before the entrance to the system's field of vision and reinforce this with further signs inside the area". The page also says it is unfair if a sign about intrusive technology is read only after the system has already captured the person. Signs should be "clearly visible and readable" and include "as a minimum basic contact details such as a website, telephone number or email address". "publishing information on a website, by itself, is not enough"; a physical sign with linked information acts as a layered privacy notice.
- **Audio:** "You should not normally use surveillance systems to directly record conversations between members of the public. This is highly intrusive". Audio should be switched off by default, used only where there is an evidenced need, and accompanied by "additional steps to make it clear to individuals that audio recording is taking place, over and above any visual recording".
- **Application to this study (my analysis):** the robot is not CCTV, but it is a camera and microphone system in a public area, so this guidance is the closest regulatory benchmark. Participants knowingly talking to a robot are different from covert conversation recording. The **bystander audio** (for example, parents chatting next to the stand) is what the ICO warns against.

### 2.4 Biometric data: are images and voice special category?

Source: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/biometric-data-guidance-biometric-recognition/key-data-protection-concepts/

- Personal information is biometric data only if it relates to physical, physiological or behavioural characteristics, "has been processed using specific technologies", and "can uniquely identify (recognise) the person".
- "Not all biometric data is automatically special category biometric data. It only becomes this if you use it to uniquely identify someone. Your purpose for processing biometric data is therefore important."
- **Caveat:** biometric data may still be another type of special category data if you **intend to infer** something like ethnicity or health from it.
- **Conclusion for this study:** pose keypoints, camera frames and voice are personal data. They are **not** special category biometric data as long as you neither identify people nor infer sensitive traits. Record this rationale in the DPIA, and do not let the LLM describe people's ethnicity, health, age or emotions (see also 3.5).

### 2.5 DPIA triggers

- **Article 35(3)(c), always a DPIA:** "a systematic monitoring of a publicly accessible area on a large scale." Among the WP29 criteria, "Systematic monitoring", "Data concerning vulnerable data subjects" and "Innovative use ... of new technological ... solutions" are all relevant: "In most cases, a combination of two of these factors indicates the need for a DPIA". https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/data-protection-impact-assessments-dpias/when-do-we-need-to-do-a-dpia/
- **ICO list of processing that requires a DPIA:** "Innovative technology ... (including AI). A DPIA is required for any intended processing operation(s) involving innovative use of technologies ... when combined with any other criterion". "Tracking ... an individual's geolocation or behaviour" is also listed, again in combination with another criterion. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/data-protection-impact-assessments-dpias/examples-of-processing-likely-to-result-in-high-risk/
- **Conclusion:** AI, behaviour tracking, children and a public space give at least 3 criteria, so a **DPIA is required**.

### 2.6 International transfer to the US (OpenAI)

- **Transfer rules (ICO brief guide, updated 15 Jan 2026):** every restricted transfer must be covered by UK adequacy regulations, appropriate safeguards (IDTA, or the Addendum to the EU SCCs), or an exception. If you use the IDTA or the Addendum, you must complete a **transfer risk assessment (TRA)**. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/a-brief-guide-to-international-transfers/
- **UK–US data bridge:** from 12 October 2023, UK organisations can transfer to US organisations certified to the "UK Extension to the EU-US Data Privacy Framework". The recipient "must be certified to the UK Extension and appear on the" DPF List. https://www.gov.uk/government/publications/uk-us-data-bridge-supporting-documents/uk-us-data-bridge-factsheet-for-uk-organisations
- **Is OpenAI certified? No, as of 3 Nov 2026.** I searched the official list at https://www.dataprivacyframework.gov/list for "OpenAI" and for "Open AI". Both returned "Query returned no results". As a control, a search for "Microsoft" returned an active entry that includes the UK Extension, so the search works.
- **What OpenAI actually relies on:** the OpenAI DPA (updated 1 Dec 2025, effective 1 Jan 2026), s.4.2, says: "Customer hereby instructs OpenAI OpCo, LLC to process any UK Data in compliance with this DPA and with the SCCs as amended by the UK Addendum". https://openai.com/policies/data-processing-addendum/ . OpenAI's EU privacy policy (updated 24 Aug 2026) also cites adequacy decisions, SCCs and "the UK International Data Transfer Addendum". https://openai.com/policies/eu-privacy-policy/
- **Consequence:** the transfer mechanism is **EU SCCs plus the UK Addendum** (Art 46), so Durham must do or document a **TRA**. Alternatively, if OpenAI approves EU data residency for the project, the data is stored and processed in the EEA (see 3.3). The EEA is covered by UK adequacy regulations according to the ICO's adequacy page (see the addendum).

### 2.7 Data (Use and Access) Act 2025 (DUAA): what matters for this study

- **All data protection provisions are in force.** On 19 June 2026 the ICO updated its guidance "to reflect that all data protection provisions in the Data (Use and Access) Act 2025 are now in force". The changes were phased in between June 2025 and June 2026. https://ico.org.uk/about-the-ico/what-we-do/legislation-we-cover/data-use-and-access-act-2025/the-data-use-and-access-act-2025-what-does-it-mean-for-organisations/
- The relevant changes, from the ICO summary at https://ico.org.uk/about-the-ico/what-we-do/legislation-we-cover/data-use-and-access-act-2025/the-data-use-and-access-act-2025-duaa-summary-of-the-changes/data-protection/ :
  - **Statutory meaning of scientific research.** It includes "fundamental or applied research, so far as these activities can reasonably be described as scientific".
  - **Broad consent** to an "area of scientific research". This applies only if the exact purpose could not be identified, the approach is consistent with recognised ethical standards, and people can consent to part of the research. It matters only if you rely on consent.
  - **Privacy-notice exemption.** You don't have to give a notice if you **further** process data for research and providing it would be impossible or a disproportionate effort. **This does not cover your initial collection at the stand.** You must still give notice when you collect.
  - **Research safeguards** were moved into one chapter of the UK GDPR, with "no substantive changes", and the text makes clear that pseudonymisation is permitted.
  - **Public task now explicitly applies only to the organisation's own tasks.** There is also a new "recognised legitimate interests" basis, which is not relevant here.
  - **Complaints:** organisations must help people complain (for example with an electronic form), acknowledge complaints within 30 days and respond "without undue delay". The privacy notice should point to Durham's complaint route.
  - **Transfer test reworded** ("not materially lower"). The ICO says this makes the law clearer "without materially changing" how personal information can be used.
- **Children's "higher protection matters" duty:** applies only to online services likely to be used by children. It is good practice for you, not a legal duty. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/children-and-the-uk-gdpr/what-should-our-general-approach-be-to-handling-children-s-personal-information/

---

## 3. OpenAI API data handling (as checked on 3–4 Nov 2026)

Main source: "Data controls in the OpenAI platform", https://developers.openai.com/api/docs/guides/your-data (https://platform.openai.com/docs/guides/your-data redirects there).

### 3.1 Training and retention

- "As of March 1, 2023, data sent to the OpenAI API is not used to train or improve OpenAI models (unless you explicitly opt in to share data with us)." Same URL.
- "By default, abuse monitoring logs are generated for all API feature usage and retained for up to 30 days, unless longer retention is required by law, or is reasonably necessary to protect our services or any third party from harm." Same URL.
- **The `/v1/realtime` row of the endpoint table reads:** data used for training = **No**; abuse monitoring retention = **30 days**; application state retention = **None**; Zero Data Retention eligible = **Yes**. Same URL.
- The Services Agreement, s.4.2, says: "OpenAI will not use Customer Content to develop or improve the Services, unless Customer explicitly agrees to such use." Under s.11.3, Customer Content is deleted within 30 days of termination. https://openai.com/policies/services-agreement/ (updated 1 Dec 2025, effective 1 Jan 2026).

### 3.2 Zero Data Retention (ZDR) and Modified Abuse Monitoring

- ZDR and MAM "are subject to prior approval by OpenAI and acceptance of additional requirements", through the sales team. ZDR excludes customer content from abuse-monitoring logs. https://developers.openai.com/api/docs/guides/your-data
- `/v1/realtime` is ZDR-eligible (table, same URL).
- **Caveat:** for ZDR/MAM customers, OpenAI "reserve[s] the right to make models ineligible ... as notified in advance" (the "Private Retention" and "Safety Retention" modes). Separately, image and file inputs to some endpoints are scanned for CSAM, and flagged images are kept for review even with ZDR. Same URL.
- **Your exposure in practice:** without ZDR, any audio or frames you send stay in OpenAI's abuse logs for up to 30 days, and **you cannot delete them on a visitor's request**. Say so in the notice.

### 3.3 Data residency (Europe / UK)

- Residency is set per project, and eligibility goes through sales. "Data residency endpoints are charged a 10% uplift for models released on or after March 5, 2026". Residency does not apply to "system data" (account, metadata, usage data). https://developers.openai.com/api/docs/guides/your-data
- **Region table:**
  - **Europe (EEA + Switzerland), `eu.api.openai.com`:** regional storage Yes, regional processing Yes, and "Requires Zero Data Retention, Modified Abuse Monitoring, Private Retention with PSP, or Safety Retention". `/v1/realtime` is listed for both storage and processing.
  - **United Kingdom, `gb.api.openai.com`:** storage Yes, **processing No**, and `/v1/realtime` is **not** in its supported services list.
  - Same URL. Markdown version: https://developers.openai.com/api/docs/guides/your-data.md
- **Endpoint support table:** `/v1/realtime` storage and processing regions are "United States, Europe (EEA + Switzerland)", and the supported models include `gpt-realtime`. One limitation: "Tracing is not currently EU data residency compliant for /v1/realtime". Same URL.
- **Recommendation:** ask OpenAI sales for ZDR plus EU data residency for a dedicated project, and turn off tracing. If they do not approve, you are on the US default with SCCs/UK Addendum and a TRA (2.6).

### 3.4 Minors and end users

- **Services Agreement s.3.3(c):** "Customer will not, and will not permit End Users to: ... (c) allow minors to use OpenAI Services without consent from their parent or guardian". Under s.3.2, the customer "will obtain and maintain from End Users any consents necessary ... to allow OpenAI to deliver the Services". An "End User" includes anyone "who uses Customer Applications". https://openai.com/policies/services-agreement/
- **Under-18 API guidance:** it defines minors as "under 18 years old" and says: "You should not use OpenAI services to process any personal data of children under 13 or the applicable age of digital consent without first implementing zero data retention in our API." Organisations serving minors should provide "age-appropriate disclosures to minors about AI tools", "age-appropriate content filters", "monitoring and reporting mechanisms, including escalation paths", and age assurance "where required or otherwise appropriate". OpenAI "reserves the right to audit". https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance
- **Usage Policies, "Keep minors safe":** for example, no exposing minors to age-inappropriate content. Current version effective 29 Oct 2025: https://openai.com/policies/usage-policies/revisions/2025-10-29/ . A new version takes effect on **20 Nov 2026** and keeps protections for "children and teens": https://openai.com/policies/usage-policies/
- OpenAI's own consumer privacy policy also says "Users under 18 must have permission from their parent or guardian to use our Services". This is for OpenAI's own services and is context only. https://openai.com/policies/eu-privacy-policy/

### 3.5 Images of people

- No OpenAI policy I found bans sending camera images of people as such.
- **The Usage Policies' "Respect privacy" section prohibits** "facial recognition databases without data subject consent", "real-time remote biometric identification in public spaces", "evaluation or classification of individuals based on their social behavior, personal traits, or biometric data (including ... inferring sensitive attributes)", and "inference regarding an individual's emotions in the workplace and educational settings, except when necessary for medical or safety reasons". This wording appears in both the 29 Oct 2025 version and the version effective 20 Nov 2026. URLs as in 3.4.
- **Consequence:** the system prompt must stop the model from identifying people, guessing age, ethnicity or emotion, or commenting on appearance. Treat the Open Day as an "educational setting" to be safe.
- The DPA says "No sensitive data is intended to be transferred unless the user includes it unexpectedly in unstructured data". https://openai.com/policies/data-processing-addendum/

### 3.6 Data Processing Addendum (DPA)

- OpenAI "acts as a Data Processor". The contracting party for UK customers is OpenAI OpCo, LLC (EEA/Swiss customers contract with OpenAI Ireland Ltd). It includes sub-processor authorisation, with the list at https://platform.openai.com/subprocessors , and deletion or return at the end of the agreement.
- Section 3.3 makes the customer responsible for "configurations and design decisions ... (e.g., retention periods, deletion, etc.)".
- UK data is covered by the SCCs plus the UK Addendum (Module Two, controller to processor). https://openai.com/policies/data-processing-addendum/
- **Action:** Durham, not the student personally, should be the contracting customer. Check with Information Governance / Procurement whether a University OpenAI account with the DPA already exists, and **do not use a personal API account**.

---

## 4. Consent model in a public space: how comparable HRI field studies did it

### 4.1 Approaches that HRI and public-display field studies have used

1. **Bu, F., Bremers, A., Colley, M., & Ju, W. (2024).** *Field Notes on Deploying Research Robots in Public Spaces.* CHI EA '24. https://doi.org/10.1145/3613905.3651044 (open version: https://arxiv.org/abs/2404.18375).
   - US public plaza, minimal-risk "altered consent".
   - For people who actively engaged and were recorded: "we sought their consent post-interaction", documented as **recorded verbal assent**, plus permission to use images.
   - "we did not request consent from passersby, who were only incidentally involved".
   - They avoided flyers and posters so as not to prime people. **That would not meet ICO signage expectations in the UK** (2.3).
   - They got written permission from the site manager, plus insurance.
2. **Brown, B., Pelikan, H., & Broth, M. (2026).** *Walking with Robots: Video Analysis of Human-Robot Interactions in Transit Spaces.* CHI '26. https://doi.org/10.1145/3772318.3791828 (open version: https://arxiv.org/abs/2602.23475).
   - European airport.
   - Researchers "wore signs showing a video camera symbol and text explaining that we were 'recording for research' (with a university logo)", and the robot carried a similar sign.
   - "we only filmed those who were interacting with the robot", and "did not keep the camera on bystanders if they seemed uncomfortable".
   - They had written permission from the airport authority.
   - They argue that consent from every passer-by is not practically feasible.
3. **Ooka, R., Takashima, K., Fujita, K., Yokosuka, Y., & Kitamura, Y. (2026).** *Effect of physical movement of robotic displays in public spaces on passersby's attraction and sustained viewing.* Quality and User Experience. https://doi.org/10.1007/s41233-026-00083-y
   - Institutional ethics committee approval. The committee required **a fence between passers-by and the robot** for safety.
   - "the registration screen for this event explicitly stated that an open experiment was being conducted".
   - A sign before the area said it "was being recorded for an open study", and a sign after it said that "the private data would be carefully treated, and we were willing to remove video data if requested (from contact information)". No removal requests were received.
   - Raw video was on password-protected storage with access limited to the authors and annotators, local copies were deleted after annotation, and footage is deleted 5 years after the experiment.
4. **Guidance from a review:** Oruma, S. O., et al. (2023). *Security Aspects of Social Robots in Public Spaces: A Systematic Mapping Study.* Sensors 23(19), 8056. https://doi.org/10.3390/s23198056 . "Robots should not record, store, or transmit personal data without explicit users' consent. If data are recorded, strong encryption should be used ... adhere to ... GDPR".

**Not found in published sources:** I found no published HRI study that used a **wearable opt-out signal** (wristband or sticker) or a **spoken "don't record me" command**. Treat these as **recommended good practice** of your own design, not established precedent.

### 4.2 Recommended model for this study: a layered "notice + opt-in to recording"

Opt-in recording is required at minimum for under-18s (Durham Safeguarding Policy, OpenAI contract), so it is simplest to apply it to everyone.

- **Layer 0, live processing, nothing stored:** the camera does pose tracking for green-clothing detection and approach, in memory only. Signs are placed **before** the camera's field of view (ICO, 2.3).
- **Layer 1, invitation:** the robot invites the visitor. Before any audio is sent to OpenAI, the robot or the researcher gives a 1-sentence disclosure and asks for an explicit "yes". Example: "I'm a research robot from Durham. I use an AI service in the US to talk. Is it OK to record our chat for research?" For anyone who looks under 18, the researcher asks whether they are 18 or over, or whether a parent/guardian is present and agrees (OpenAI s.3.3(c)).
- **Layer 2, study consent:** a short tick-box or tablet consent covering recording, the questionnaire, and use of anonymised data. The parent/guardian consents for under-18s. Durham's safeguarding rule is written consent, "where appropriate".
- **Visitors who say no, and unaccompanied under-18s:** offer a **non-recorded, non-OpenAI demo** (scripted local wave or greeting) so nobody is excluded from the fun.
- **Withdrawal:** possible on the spot (see the opt-out section of the checklist) and afterwards using a visit code card. Explain that data already sent to OpenAI may remain in OpenAI's abuse logs for up to 30 days unless ZDR is enabled.

---

## 5. Paste-ready checklist for the Durham ethics form

Legend:
- **[REQ]**: required by an official source (URL given).
- **[REC]**: recommended good practice. Some [REC] items are my inference from an official source; where so, the source is noted.

### A. Participants and under-18s

- [ ] **[REQ]** Submit the study for ethics review in the Ethics and Research Integrity Portal before any data collection. Supervisor = PI. Approval is needed for any significant amendment. Research Integrity Policy s.7.3–7.5, https://www.durham.ac.uk/research/ethics--governance/research-integrity-policy-and-code-of-good-practice/
- [ ] **[REQ]** Name the participant groups: adult visitors, parents/guardians, and young people aged 16–17. Identify minors as a potentially vulnerable group and describe the safeguarding arrangements. Same policy, s.7.8.3–7.8.5.
- [ ] **[REQ]** Get parent/guardian consent before any under-18 uses the OpenAI-powered conversation. OpenAI Services Agreement s.3.3(c), https://openai.com/policies/services-agreement/
- [ ] **[REQ]** Do not process personal data of under-13s through OpenAI unless ZDR is enabled. OpenAI Under-18 guidance, https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance
  - **[REC]** Exclude under-16s from the recorded, OpenAI-powered conversation altogether. Younger siblings get the non-recorded local demo.
- [ ] **[REQ]** Get written consent before making video or audio recordings of a child (from the parent/guardian), "where appropriate". Durham Safeguarding Policy and Procedures 2025, Appendix A, https://www.durham.ac.uk/media/durham-university/support-services-/student-support-and-wellbeing/student-conduct/Safeguarding-Policy-and-Procedures-2025.pdf
- [ ] **[REQ]** Researchers work in an open, observable environment and are never alone with a child. Same policy, Appendix A.
- [ ] **[REQ]** Ask the department whether a DBS check is required for the researchers at the stand. Durham says safeguarding "may include" DBS. Research Integrity Policy s.7.8.5; https://www.durham.ac.uk/about-us/safeguarding/dbs/
  - **[REC]** Complete Durham safeguarding training (https://www.durham.ac.uk/about-us/safeguarding/), know the reporting route for disclosures, and have one named safeguarding lead at the stand.
- [ ] **[REC]** Age check: "Are you 18 or over? If not, is a parent/guardian here with you?" Asked verbally by the researcher. No ID checks, and age is not stored beyond an age band (under-18 / 18+).
- [ ] **[REC]** Treat 16–17-year-olds as competent to agree for themselves to the **non-OpenAI** parts, such as the anonymous questionnaire, in line with ICO competence guidance (https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/children-and-the-uk-gdpr/how-do-the-lawful-bases-apply-to-children-s-personal-information/). Confirm this against Durham's internal toolkit.

### B. Information and consent (signage text suggestions)

- [ ] **[REQ]** Put signs **before** visitors enter the camera's field of view, with more signs at the stand. They must be clearly visible and readable, say who runs the system, why, and how to contact them, and link to more information (layered notice). A website alone is not enough. ICO surveillance guidance, https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/cctv-and-video-surveillance/guidance-on-video-surveillance-including-cctv/how-can-we-comply-with-the-data-protection-principles-when-using-surveillance-systems/
- [ ] **[REQ]** Take extra steps to make audio recording clear, beyond the visual signage. Same ICO URL.
  - **[REC]** An on-robot "recording" light or screen icon, plus a spoken line at the start of each chat.
- [ ] **[REQ]** Provide a tailored privacy notice (Durham Part 2 format), with an age-appropriate version for young people. It must cover:
  - controller: Durham University;
  - lawful basis: public task (research);
  - what is recorded;
  - OpenAI as processor, the US transfer and its safeguard, and OpenAI's 30-day abuse-log retention;
  - retention periods;
  - rights and how to withdraw;
  - the DPO/Information Governance contact (info.access@durham.ac.uk);
  - the complaint route, including the ICO.
  
  Sources:
  - Durham notice format: https://www.durham.ac.uk/about-us/governance/information-governance/privacy-notices/researchers/
  - ICO children's guidance: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/childrens-information/children-and-the-uk-gdpr/what-should-our-general-approach-be-to-handling-children-s-personal-information/
  - DUAA complaints: https://ico.org.uk/about-the-ico/what-we-do/legislation-we-cover/data-use-and-access-act-2025/the-data-use-and-access-act-2025-what-does-it-mean-for-organisations/
- [ ] **[REQ]** Tell participants, when they consent, how their data will be anonymised, used and stored, including possible future research use. RDM Policy s.5.5, https://www.durham.ac.uk/research/ethics--governance/research-data-management-policy/
- [ ] **[REQ]** Give an age-appropriate disclosure that the robot is an AI and how it works (OpenAI Under-18 guidance, URL above).
  - **[REC]** Tell everyone, not just minors.
- [ ] **[REC]** Ask the Open Day organisers to add a line to the registration or confirmation email and the printed programme. Precedent: Ooka et al. 2026, https://doi.org/10.1007/s41233-026-00083-y
- [ ] **[REC]** Suggested signage wording (A2 sign at the approach plus an A4 sign on the stand; large font, camera and microphone icons, Durham logo):

  > **Research robot – camera and microphone in use**
  > This Durham University (Department of Computer Science) research stand studies how people respond to a talking robot.
  > • The robot's camera tracks body position (stick-figure "skeleton") to notice people nearby. **No face recognition. We do not identify anyone.**
  > • The robot may invite people wearing **green** to come over. You can simply walk on.
  > • **Nothing you say is recorded unless you agree at the stand.** If you agree, we record the conversation (audio, transcript, and occasional pictures from the robot's camera) for research.
  > • To talk, the robot sends your voice and occasional camera pictures to **OpenAI (USA)**, which may keep them for up to 30 days for safety checks. They are not used to train AI.
  > • **Under 18? You need a parent or guardian with you to say yes.**
  > • Change your mind? Say **"stop recording"**, press the red button, or ask the researcher. We will delete your recording on the spot.
  > • More information and privacy notice: [QR code / short URL] · Contact: [researcher email] · Data Protection: info.access@durham.ac.uk · Ethics ref: [number]

- [ ] **[REC]** Randomised openers: describe them in the information sheet in general terms ("the robot's greeting varies between visitors as part of the study"). Then the design does not count as deception, which Durham lists as a risk factor (Research Integrity Policy s.7.8.4). No individual debrief is needed beyond this.

### C. Opt-out and withdrawal mechanisms

- [ ] **[REC]** Default is **no recording** until the visitor gives an explicit yes (opt-in). Pose tracking runs in memory only and its output is not stored for people who do not take part. This follows the ICO guidance that audio should be off by default (https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/cctv-and-video-surveillance/guidance-on-video-surveillance-including-cctv/how-can-we-comply-with-the-data-protection-principles-when-using-surveillance-systems/).
- [ ] **[REC]** A spoken command ("stop recording" / "don't record me") ends the session and deletes the current visit's local files. Test the keyword detection locally, not via OpenAI.
- [ ] **[REC]** A physical red **privacy button** on the stand that pauses camera and microphone capture, with a visible indicator.
- [ ] **[REC]** An optional "**no-photo**" sticker or lanyard, if the Open Day already uses one. Researchers then decline to record that visitor.
  - **Caution:** do not build automatic sticker detection. It would mean extra image analysis and could fail silently.
- [ ] **[REC]** **Deletion at the stand:** each recorded visit gets a short random visit ID, shown on screen and printed on a card. The researcher can delete that folder immediately on request; log the deletion without personal data. The card carries an email address for later withdrawal up to a stated date, for example until the data is anonymised.
- [ ] **[REQ]** Tell visitors honestly about the limits of withdrawal: data already sent to OpenAI stays in abuse-monitoring logs for up to 30 days unless ZDR is enabled. https://developers.openai.com/api/docs/guides/your-data
- [ ] **[REC]** **Bystanders:**
  - limit the camera's field of view to the interaction zone and tape a floor marking for it;
  - do not store frames or track logs of people who have not consented;
  - if a stored frame shows a bystander, blur or crop them before analysis;
  - use a close-talk or directional microphone with voice-activity gating, so passers-by's conversations are not recorded.
  
  These steps mirror the ICO audio guidance (same URL) and Brown et al. 2026 (https://doi.org/10.1145/3772318.3791828).

### D. Third-party processor (OpenAI) and international transfer

- [ ] **[REQ]** Use OpenAI only under a Durham-held account with the OpenAI DPA in place, with OpenAI as processor. Check sub-processors at https://platform.openai.com/subprocessors . DPA: https://openai.com/policies/data-processing-addendum/
- [ ] **[REQ]** Identify the transfer mechanism. OpenAI is **not** DPF/UK Extension certified: the https://www.dataprivacyframework.gov/list search returned no results on 3 Nov 2026. The safeguard is therefore the **EU SCCs plus the ICO UK Addendum** (DPA s.4.2). Complete or attach a **transfer risk assessment**. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/a-brief-guide-to-international-transfers/
- [ ] **[REC]** Ask OpenAI for **Zero Data Retention** and **EU data residency** (`eu.api.openai.com`; `/v1/realtime` and `gpt-realtime` are supported; ZDR/MAM required). Disable tracing. The UK region does not support Realtime. https://developers.openai.com/api/docs/guides/your-data
- [ ] **[REQ]** Do not use OpenAI for facial recognition, biometric identification, classifying people by personal traits, inferring sensitive attributes, or inferring emotions in an educational setting. OpenAI Usage Policies, https://openai.com/policies/usage-policies/
  - **[REC]** Write the system prompt to forbid describing people's appearance, age, ethnicity, health or emotions, and to stay on safe, age-appropriate topics.
- [ ] **[REQ]** Keep content age-appropriate for minors: use content filtering, monitoring, and an escalation path with a human researcher present. OpenAI Under-18 guidance (URL above); Usage Policies "Keep minors safe".
- [ ] **[REC]** Send camera frames to OpenAI only when needed for the conversation. Downscale them, crop them to the participant, and never send frames of people who have not consented. Send audio only during an active, consented session.
- [ ] **[REC]** Use OpenAI's latest realtime model snapshot. OpenAI recommends the latest flagship models when serving minors (Under-18 guidance).

### E. Data minimisation: what to record and what NOT to record

- [ ] **[REQ]** Data protection by design: informed consent over storage and sharing, and provision for fully anonymised storage. RDM Policy s.7.3.3, https://www.durham.ac.uk/research/ethics--governance/research-data-management-policy/
- [ ] **[REC]** **Record (consenting participants only):**
  - visit ID;
  - timestamp;
  - opener condition;
  - age band (under-18 / 18+) and consent type (self, or parent/guardian);
  - conversation transcript (redact names and other identifiers);
  - robot utterances;
  - session audio (only if your analysis truly needs it, for example prosody or turn-taking; otherwise keep only the transcript);
  - 5 Hz pose-keypoint track log (anonymous skeleton coordinates);
  - questionnaire responses linked by visit ID.
- [ ] **[REC]** **Do NOT record:**
  - the continuous camera stream;
  - a camera frame every 2 s for everyone; replace this with no stored frames, or frames for consenting participants only, with faces blurred at capture if possible;
  - audio outside an active, consented session;
  - track logs of non-participants (keep only aggregate counts, such as the number of passers-by and the number invited);
  - names, emails or contact details, unless someone separately asks to be contacted, and then store them apart from the data;
  - any face embeddings or re-identification features;
  - inferred age, gender, ethnicity or emotion.
- [ ] **[REC]** Treat green-clothing detection as colour detection on the tracked body region, done locally. Store only "invited: yes/no", not images.

### F. Retention and deletion schedule

- [ ] **[REQ]** Submit a DMP (DMPonline) and register the data with the University. Give an approved destruction date, and record the deletion date and reason in the metadata. RDM Policy s.5.5, 7.2.1, 7.7.2 (URL above).
- [ ] **[REQ]** Default retention for source research data is 10 years after publication or the end of data collection. A shorter period for raw identifiable data can be justified on ethical grounds. RDM Policy s.7.6.1.
- [ ] **[REC]** Proposed schedule:
  - **Robot disk:** raw files are moved to Durham secure storage at the end of each Open Day and **securely wiped from the robot the same day**.
  - **Raw audio and any stored frames:** deleted as soon as transcription, redaction and annotation are complete, and **at most 6 months** after collection. Benchmarks: Durham CCTV keeps footage 28 days (https://www.durham.ac.uk/about-us/governance/information-governance/privacy-notices/cctv/); Ooka et al. keep video 5 years. Choose and justify your own period.
  - **Pseudonymised transcripts, track logs and questionnaire data:** pseudonymised until analysis is finished, then anonymised (remove the link between visit ID and consent records).
  - **Anonymised derived data:** keep for 10 years per RDM s.7.6.1, and deposit in a repository where appropriate.
  - **Consent forms:** keep separately, for the same period as the data they authorise.
  - **OpenAI copies:** up to 30 days in abuse logs, or none with ZDR (https://developers.openai.com/api/docs/guides/your-data).
  - **Withdrawal:** possible until anonymisation, at a date stated in the information sheet.

### G. Security: encryption and who has access

- [ ] **[REQ]** Follow the University Information Security Policy, and keep data "Stored securely and protected from loss". RDM Policy s.7.3.1 and s.7.4.1.
- [ ] **[REC]** Use full-disk encryption on the robot or onboard PC (LUKS or FileVault) and on any laptop used.
- [ ] **[REC]** Transfer data only to Durham-managed storage with access limited to named people (the student, the supervisor, and named annotators). No personal cloud drives and no USB sticks; if a USB stick is unavoidable, use an encrypted one.
- [ ] **[REC]** Store the API key in a secrets store, not in code. Restrict the API project to the Realtime endpoint, set spend limits, and limit dashboard access to the student and supervisor.
- [ ] **[REC]** Lock the robot's screen and terminal. The stand is a public area, so never leave the laptop unattended.
- [ ] **[REQ]** Have a breach plan: report incidents to the Information Governance Unit (info.access@durham.ac.uk, https://www.durham.ac.uk/about-us/governance/information-governance/).

### H. No face recognition / no identification statement

- [ ] **[REQ]** Document why the data is not special category biometric data: it is not used to uniquely identify anyone, and no sensitive traits are inferred. ICO biometric guidance, https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/biometric-data-guidance-biometric-recognition/key-data-protection-concepts/
- [ ] **[REC]** Suggested statement for the form: "The system does not perform face recognition, face matching, voice identification or re-identification of any kind. The camera is used only for real-time body-pose estimation (keypoints) and clothing-colour detection, in order to approach and address a person. No biometric templates are created or stored. The language model is instructed not to describe or infer identity, age, gender, ethnicity, health or emotion, and OpenAI's Usage Policies prohibit such uses. Track IDs are temporary and reset between visits, and they are not linked to any identity."

### I. Risk assessment: robot safety, crowding, safeguarding

- [ ] **[REQ]** Complete a health and safety risk assessment as part of departmental governance, and safeguard the wellbeing of participants and others. Research Integrity Policy s.4/7.10 ("health and safety risk assessment"), https://www.durham.ac.uk/research/ethics--governance/research-integrity-policy-and-code-of-good-practice/
- [ ] **[REC]** Robot safety, even with locomotion disabled:
  - secure the robot to a stand or gantry so it cannot topple;
  - limit arm and gesture speed and range;
  - keep an E-stop within reach of the researcher at all times;
  - set up a **barrier or keep-out zone** of about 1 m. Precedent: an ethics committee required a fence in Ooka et al. 2026 (https://doi.org/10.1007/s41233-026-00083-y);
  - follow battery charging and storage rules;
  - manage cables against trip hazards;
  - display a "please do not touch the robot" sign.
- [ ] **[REC]** Crowding: put the stand where queues will not block a corridor or fire exit. Stop invitations when more than N people are waiting. Agree the location with the Open Day organisers and site management. Precedent: written site permission in Bu et al. 2024 and Brown et al. 2026.
- [ ] **[REQ]** Safeguarding:
  - at least one researcher is always present and visible;
  - follow the disclosure procedure if a young person discloses harm;
  - follow content-safety measures for minors.
  
  Durham Safeguarding Policy 2025 (URL above); OpenAI Under-18 guidance (URL above).
- [ ] **[REC]** Plan for LLM failure modes: inappropriate or incorrect output, or the model giving advice. Use a short maximum session length (about 1 minute), keep a topic whitelist in the system prompt, keep a manual "end conversation" key, and log incidents.
- [ ] **[REC]** Distress or discomfort: anyone can end the conversation at any time. The researcher watches for discomfort, for example a younger child who is approached because they are wearing green.
- [ ] **[REQ]** Check insurance for robots in public-facing activities. The portal checklist signposts insurance (https://www.durham.ac.uk/research/ethics--governance/2024-research-integrity-statement/).

### J. Questionnaire

- [ ] **[REC]** Make it optional, short (under 2 minutes) and anonymous. Do not collect names or emails. Use age band only.
- [ ] **[REC]** Link it to the interaction only through the visit ID on the card or screen. Explain this link in the information sheet so the participant can withdraw both together.
- [ ] **[REQ]** Use age-appropriate wording for 16–17-year-olds. ICO children's guidance (URL in B).
  - **[REC]** Pilot it with 2–3 people.
- [ ] **[REC]** Use a Durham-approved survey tool (for example the University's licensed platform), or paper or a tablet that saves locally to the encrypted device. Do not use an unvetted third-party form.
- [ ] **[REC]** Include no free-text questions that invite sensitive information. Allow "prefer not to say".
- [ ] **[REQ]** If the questionnaire collects data that is reused beyond what the notice describes, update the notice. The DUAA research exemption from notices covers further processing only, not collection. https://ico.org.uk/about-the-ico/what-we-do/legislation-we-cover/data-use-and-access-act-2025/the-data-use-and-access-act-2025-duaa-summary-of-the-changes/data-protection/

### K. DPIA (cross-cutting)

- [ ] **[REQ]** Complete a DPIA and have the Information Governance Unit review it before the Open Day. Triggers:
  - surveillance system (ICO);
  - AI/innovative technology plus tracking, children and a public space (ICO list and Art 35(3)(c));
  - Durham s.7.8.6.
  
  Sources:
  - https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/data-protection-impact-assessments-dpias/examples-of-processing-likely-to-result-in-high-risk/
  - https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/data-protection-impact-assessments-dpias/when-do-we-need-to-do-a-dpia/
  - https://www.durham.ac.uk/about-us/governance/information-governance/
- [ ] **[REQ]** State the lawful basis: UK GDPR Art 6(1)(e), public task (research). Keep ethical consent separate from GDPR consent. ICO research provisions, https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/the-research-provisions/principles-and-grounds-for-processing/ ; Durham General Privacy Notice, https://www.durham.ac.uk/about-us/governance/information-governance/privacy-notices/general-privacy-notice/

---

## 6. Gaps: what I could not verify (ask locally)

| Item | Status | Where to ask |
|---|---|---|
| Ethics review turnaround time | Not public; internal SharePoint (SSO) | Department ethics chair; https://durhamuniversity.sharepoint.com/teams/ResearchEthicsGovernance |
| Durham rule on 16–17-year-olds consenting alone | Not public | Same toolkit, or department ethics chair |
| Durham research-participant privacy notice and DPIA templates | Not public | info.access@durham.ac.uk |
| Open Day photography/filming rules | Not found publicly | Student Recruitment / Open Day team |
| Whether Durham already has an OpenAI enterprise agreement and DPA | Not public | Information Governance / Procurement / CIS |
| OpenAI ZDR and EU-residency approval for your project | Needs a request to OpenAI sales | Through the Durham account holder |
| Published HRI precedent for opt-out stickers or "don't record me" voice commands | None found | Treat as your own design, and explain it in the form |

---

## Addendum: further verification (appended as checks complete)

- **4 Nov 2026: Faculty confirmed.** Durham's academic departments page lists the Faculty of Science departments as "Biosciences, Chemistry, Computer Science, Earth Sciences, Engineering, Mathematical Sciences, Physics, Psychology". https://www.durham.ac.uk/departments/academic/ . So whether you are based in CS or Engineering, review is by your department's ethics sub-committee, with assurance going to the Faculty of Science ethics committee.
- **4 Nov 2026: EEA adequacy confirmed.** The ICO says "All the countries in the European Economic Area (EEA) have full adequacy", and this includes Ireland. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/adequacy-regulations/is-the-restricted-transfer-covered-by-adequacy-regulations/ . If OpenAI approves EU data residency, storage and inference for `/v1/realtime` happen in the EEA, which UK adequacy regulations cover. Your contract counterparty is still OpenAI OpCo, LLC (US) under the DPA, and "system data" can still leave the region. Record both points in the DPIA and the TRA.
- **4 Nov 2026: UK Extension mechanics confirmed.** You may "only make a restricted transfer to a US business that has an active status on the DPF list". You must check that the recipient "is signed up to the UK Extension" and that the certification is active. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/adequacy-regulations/how-does-the-uk-extension-to-the-eu-us-data-privacy-framework-work/ . OpenAI had no DPF entry on 3 Nov 2026 (section 2.6), so the data bridge does not apply. Re-check the list just before the Open Day.
- **Browser note.** openai.com and durham.ac.uk return HTTP 403 to automated fetchers. I read the OpenAI pages in a real browser on 3 Nov 2026. If a reviewer cannot open a link, the pages are still public.
