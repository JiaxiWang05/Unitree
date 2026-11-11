# Related-work scan: a stationary humanoid greeter at a university Open Day

Project: a Unitree G1 that never moves; YOLO pose tracking; the robot speaks first when someone 1.2–2.2 m away faces it, with a camera-grounded opener that names their clothing; then about one minute of chat with OpenAI gpt-realtime (speech-to-speech + frames); funnel logged as noticed → invited → accepted → conversation → goodbye/drop-off; randomised opener conditions.

Status: complete, 2026-11-04. 51 main entries plus sub-entries, all verified.

**How each reference was checked.** Every entry below was looked up by DOI or arXiv ID on a live record:
- Crossref (api.crossref.org) for title, authors, venue and year.
- OpenAlex (api.openalex.org) or the publisher's or institution's page for the abstract.
- arXiv items on the arXiv API or abs page.
- A sample of DOIs resolve at doi.org (spot-checked).

Summaries only say what the abstract or landing page says. "★" marks the 34 I would cite first; the other 17 main entries (plus sub-entries) are supporting references.

---

## 1. Robots that start interactions or greet people in public spaces

- ★ **Kanda, T., Shiomi, M., Miyashita, Z., Ishiguro, H., Hagita, N. (2010). A Communication Robot in a Shopping Mall.** *IEEE Transactions on Robotics* 26(5). https://doi.org/10.1109/TRO.2010.2062550
  A Robovie in a mall ran for 25 days and logged 2,642 interactions. It used floor sensors to detect people and start interaction, RFID to recognise registered visitors, and partial teleoperation instead of speech recognition. Visitors found it acceptable, and the amount of teleoperation needed fell over time. (Companion HRI'09 paper: "An affective guide robot in a shopping mall", https://doi.org/10.1145/1514095.1514127.)

- ★ **Satake, S., Kanda, T., Glas, D. F., Imai, M., Ishiguro, H., Hagita, N. (2009). How to approach humans? Strategies for social robots to initiate interaction.** *HRI 2009*. https://doi.org/10.1145/1514095.1514117
  Built from failures in a real mall: people were sometimes unaware the robot was talking to them, or unsure it meant to start a conversation. The resulting model predicts walking paths, picks a target, plans an approach and signals intent nonverbally. In a field trial it significantly improved the success of starting conversations. (Japanese journal version: JRSJ 2010, https://doi.org/10.7210/jrsj.28.327.)

- **Shiomi, M., Kanda, T., Ishiguro, H., Hagita, N. (2006). Interactive humanoid robots for a science museum.** *HRI 2006*. https://doi.org/10.1145/1121241.1121293
  This was a two-month field trial, with RFID-tagged visitors and robots that combined "free play" chat with exhibit guiding. Visitors rated the robots highly, and an in-trial comparison of three operating conditions found that combining free play with guiding gave the best visitor experience.

- ★ **Gockley, R., Bruce, A., Forlizzi, J., Michalowski, M., Mundell, A., Rosenthal, S., et al. (2005). Designing robots for long-term social interaction.** *IROS 2005*. https://doi.org/10.1109/IROS.2005.1545303
  Valerie the "roboceptionist" was installed permanently in a CMU building entrance. Over nine months many visitors came back daily, but few interactions lasted more than 30 seconds. This is a useful baseline for your roughly one-minute target.

- **Hayashi, K., Sakamoto, D., Kanda, T., Shiomi, M., Koizumi, S., Ishiguro, H., Hagita, N. (2007). Humanoid robots as a passive-social medium: a field experiment at a train station.** *HRI 2007*. https://doi.org/10.1145/1228716.1228735
  Two robots talked to each other, not to passengers, to draw interest to information at a train station. They ran for eight days to test this "passive-social" alternative to direct interaction.

- ★ **Kato, Y., Kanda, T., Ishiguro, H. (2015). May I help you? Design of human-like polite approaching behavior.** *HRI 2015*. https://doi.org/10.1145/2696454.2696463
  This study asks when a robot should start an interaction, and argues against both "talk to everyone" and "wait to be addressed". The authors modelled mall staff who respond to visitors' intentions with small approach and "availability" behaviours. On a robot in a real mall the model was less intrusive and still started interactions.

- ★ **Pitsch, K., Kuzuoka, H., Suzuki, Y., Süssenbach, L., Luff, P., Heath, C. (2009). "The first five seconds": Contingent stepwise entry into an interaction as a means to secure sustained engagement in HRI.** *RO-MAN 2009*. https://doi.org/10.1109/ROMAN.2009.5326167
  Drawing on Conversation Analysis, this paper treats the opening as a stepwise, mutually adjusted process. It compared a contingent with a non-contingent entry, and users who entered contingently interacted with the robot in significantly different ways.

- **Gehle, R., Pitsch, K., Dankert, T., Wrede, S. (2017). How to open an interaction between robot and museum visitor? Strategies to establish a focused encounter in HRI.** *HRI 2017*. https://doi.org/10.1145/2909824.3020219
  The authors used a Wizard-of-Oz museum-guide corpus to study when the robot should look at, then verbally greet, a visitor ("pre-beginnings"). They identified features that separate two visitor types, each needing its own opening strategy.

- ★ **Foster, M. E., Alami, R., Gestranius, O., Lemon, O., Niemelä, M., Odobez, J.-M., Pandey, A. K. (2016). The MuMMER project: Engaging human-robot interaction in real-world public spaces.** *ICSR 2016, LNCS 9979*, pp. 753–763. https://doi.org/10.1007/978-3-319-47437-3_74
  This is the project overview for Pepper in a shopping mall; only the metadata was checked, as no abstract was retrievable. The later system paper is Foster, M. E., Craenen, B., Deshmukh, A., Lemon, O., Bastianelli, E., et al. (2019), *MuMMER: Socially Intelligent Human-Robot Interaction in Public Spaces*, arXiv:1909.06749 (https://arxiv.org/abs/1909.06749). It integrates audio-visual sensing, social signal processing, dialogue and navigation in ROS, and was deployed with customers in a shopping mall in Finland.

- ★ **Aaltonen, I., Arvola, A., Heikkilä, P., Lammi, H. (2017). Hello Pepper, may I tickle you? Children's and adults' responses to an entertainment robot at a shopping mall.** *HRI 2017 Companion*. https://doi.org/10.1145/3029798.3038362
  This was one day with Pepper in a mall. Children crowded the robot once others, especially adults, were already interacting, and they enjoyed playful activities. Adults wanted useful functions and spoke to it like a speech-recognition machine. (Same mall programme, acceptance surveys: Niemelä et al., HRI'17 Companion, https://doi.org/10.1145/3029798.3038333.)

- **Šabanović, S., Michalowski, M. P., Simmons, R. (2006). Robots in the wild: observing human-robot social interaction outside the lab.** *IEEE AMC 2006*. https://doi.org/10.1109/AMC.2006.1631758
  This paper argues for observational field studies. It illustrates the case with a conference-attending robot and a stationary robotic receptionist, and shows how observation reveals unanticipated aspects of interaction.

- **Jung, M., Hinds, P. (2018). Robots in the Wild: A Time for More Robust Theories of Human-Robot Interaction.** *ACM THRI* 7(1), Article 2, pp. 1–5. https://doi.org/10.1145/3208975
  This is a guest editorial for a THRI special issue on in-the-wild HRI. Only the metadata and title were verified; no abstract is available. It is the standard citation for why field work should build theory.

- ★ **Lee, M. K., Forlizzi, J., Kiesler, S., Rybski, P., Antanitis, J., Savetsila, S. (2012). Personalization in HRI: A longitudinal field experiment.** *HRI 2012*. https://doi.org/10.1145/2157689.2157804
  Snackbot ran a four-month field experiment, with half of the participants getting service personalised to their usage and interactions. Adding personalisation improved rapport, cooperation and engagement compared with the social service alone.

- ★ **Saad, E., Neerincx, M. A., Hindriks, K. V. (2019). Welcoming robot behaviors for drawing attention.** *HRI 2019 (LBR)*, pp. 636–637. https://doi.org/10.1109/HRI.2019.8673283
  Pepper acted as a welcoming robot at a **university building entrance**, triggered automatically by people detection on head keypoints, which is very close to your sensing pipeline. It showed a wave, an utterance, movement or combinations. With N=364 passers-by and 28 interviews, combined modalities drew more attention, but people often did not remember what the robot said.

- ★ **Fischer, K., Soto, B., Pantofaru, C., Takayama, L. (2014). Initiating interactions in order to get help: Effects of social framing on people's responses to robots' requests for assistance.** *RO-MAN 2014*. https://doi.org/10.1109/ROMAN.2014.6926383
  The robot opened either with an acoustic signal or with a verbal greeting. The greeting ("social framing") held attention and made the robot seem friendlier, but barely changed willingness to help, which depended more on what people were doing.

- **Bohus, D., Saw, C. W., Horvitz, E. (2014). Directions robot: in-the-wild experiences and lessons learned.** *AAMAS 2014*. https://doi.org/10.65109/kapi6982 (resolves to ACM DL)
  A gesturing humanoid that gave directions was deployed in an office building. The authors report challenges with managing engagement, giving directions and handling out-of-domain queries in open, multiparty settings.

- **Liu, P., Glas, D. F., Kanda, T., Ishiguro, H. (2018). Learning proactive behavior for interactive social robots.** *Autonomous Robots* 42, 1067–1085 (online 2017). https://doi.org/10.1007/s10514-017-9671-8
  The robot learns both human-initiated and robot-initiated (proactive) behaviour from human–human shop interactions, in a camera-shop scenario. The learned behaviours were rated more proactive and more socially appropriate. (Abstract content checked via search snippets; the publisher page was not reachable.)

## 2. Personalised or context-aware openers, compliments and flattery, privacy

- ★ **Glas, D. F., Wada, K., Shiomi, M., Kanda, T., Ishiguro, H., Hagita, N. (2017). Personal Greetings: Personalizing Robot Utterances Based on Novelty of Observed Behavior.** *International Journal of Social Robotics* 9, 181–198 (online 2016). https://doi.org/10.1007/s12369-016-0385-4
  **This is the closest precedent for "name something you notice about them".** Sensors track a person's appearance or behaviour, and the robot comments on what is new (for example a new hairstyle) or habitual (for example visiting every afternoon). Classifiers matched human judgements of novelty (88%) and topic (95%). A teleoperated robot greeted mall customers for three weeks, and interviewees appreciated the personal greetings. Differences from your project: the visitors were repeat customers, the robot was teleoperated, and the openers were not LLM-generated or randomised against a generic opener. (Abstract content checked via search snippets; the Springer page was not reachable.)

- ★ **Fogg, B. J., Nass, C. (1997). Silicon sycophants: the effects of computers that flatter.** *International Journal of Human-Computer Studies* 46(5). https://doi.org/10.1006/ijhc.1996.0104
  In a lab study (N=41), participants received sincere praise, flattery or generic feedback from a computer. Flattered participants reported more positive affect and evaluations even though they knew the flattery was noncontingent, and sincere praise worked like flattery.

- **Kaptein, M., Markopoulos, P., de Ruyter, B., Aarts, E. (2010, online). Two acts of social intelligence: the effects of mimicry and social praise on the evaluation of an artificial agent.** *AI & Society*. https://doi.org/10.1007/s00146-010-0304-4
  In an experiment (N=50) with a chat robot, social praise (positive feedback about the ongoing conversation) raised perceived friendliness, and mimicry raised perceived intelligence.

- ★ **Chai, D., Li, J., Huang, J. (2026). Machine talk: When flattery sounds better from a bot.** *Journal of Retailing and Consumer Services* 88, 104465. https://doi.org/10.1016/j.jretconser.2025.104465
  Across five studies, consumers were more open to flattery from service robots than from human staff, but preferred praise from humans. The authors explain this by motive: people read human flattery as self-serving and assume robots have no motive. Making the robot's "thinking" visible restored a preference for praise. This is relevant if your clothing opener reads as a compliment. (Abstract checked on the BUAA institutional page.)

- ★ **Heenan, B., Greenberg, S., Aghel-Manesh, S., Sharlin, E. (2014). Designing social greetings in human robot interaction.** *DIS 2014*. https://doi.org/10.1145/2598510.2598513
  Kendon's greeting sequence and Hall's proxemics were turned into a state machine on a NAO (distance salutation, approach, close salutation), which the authors argue makes greetings socially understandable. It is useful for framing your 1.2–2.2 m trigger zone and "come stand on the spot" invitation.

- ★ **Lutz, C., Tamò-Larrieux, A. (2020). The Robot Privacy Paradox: Understanding How Privacy Concerns Shape Intentions to Use Social Robots.** *Human-Machine Communication* 1. https://doi.org/10.30658/hmc.1.6
  In a survey, respondents worried most about data protection by manufacturers, then about social and physical privacy. Perceived benefits outweighed privacy concerns (a "privacy paradox"). This is relevant to a camera robot that comments on what people wear.

- **Rueben, M., Aroyo, A. M., Lutz, C., Schmölz, J., Van Cleynenbreugel, P., Corti, A., et al. (2018). Themes and research directions in privacy-sensitive robotics.** *IEEE ARSO 2018*. https://doi.org/10.1109/ARSO.2018.8625758
  A workshop roadmap with seven themes, including data privacy, manipulation and deception, trust, and legal issues.

## 3. Detecting approach and engagement; proxemics

- ★ **Michalowski, M. P., Šabanović, S., Simmons, R. (2006). A spatial model of engagement for a social robot.** *IEEE AMC 2006*. https://doi.org/10.1109/AMC.2006.1631755
  This work grades engagement from laser-tracked position and camera head pose, on the Valerie roboceptionist. Observational analysis suggested giving more weight to movement and varying the timing of behaviours. It is the direct ancestor of your "distance + facing" trigger.

- **Sidner, C. L., Lee, C., Kidd, C. D., Lesh, N., Rich, C. (2005). Explorations in engagement for humans and robots.** *Artificial Intelligence* 166(1–2), 140–164. https://doi.org/10.1016/j.artint.2005.03.005 (preprint: https://arxiv.org/abs/cs/0507056)
  The paper defines engagement as starting, maintaining and ending a perceived connection. With engagement gestures such as face tracking, people looked at the robot more often and found the interaction more appropriate.

- ★ **Bohus, D., Horvitz, E. (2009). Models for multiparty engagement in open-world dialog.** *SIGDIAL 2009*. https://doi.org/10.3115/1708376.1708409
  Models for sensing engagement state, deciding whom to engage and when, and rendering that as behaviour. They were evaluated with an embodied agent "in the wild".
  - Companion paper: **Bohus & Horvitz (2009), Learning to predict engagement with a spoken dialog system in open-world settings**, *SIGDIAL 2009*, https://doi.org/10.3115/1708376.1708411. Self-supervised models predicted engagement intention from spatiotemporal and attention features 3–4 s before it happened, with 2–4% false positives.
  - **Bohus & Horvitz (2014), Managing human-robot engagement with forecasts and... um... hesitations**, *ICMI 2014*, https://doi.org/10.1145/2663204.2663241. The robot forecasts disengagement and uses hesitations when uncertain; tested on the in-the-wild directions robot.

- ★ **Foster, M. E., Gaschler, A., Giuliani, M. (2017). Automatically classifying user engagement for dynamic multi-party human–robot interaction.** *International Journal of Social Robotics*. https://doi.org/10.1007/s12369-017-0414-y
  For a robot bartender, a simple rule-based classifier built from observed human behaviour generalised to new data better than trained classifiers. All the classifiers changed their estimate too often, and a CRF improved stability. This supports a simple distance-and-facing rule.

- **Ben-Youssef, A., Clavel, C., Essid, S., Bilac, M., Chamoux, M., Lim, A. (2017). UE-HRI: a new dataset for the study of user engagement in spontaneous human-robot interactions.** *ICMI 2017*. https://doi.org/10.1145/3136755.3136814
  A public dataset of 54 spontaneous conversations with Pepper in a public space. The robot started the conversation automatically on detecting someone, and people were free to leave at any time.

- ★ **Oertel, C., Castellano, G., Chetouani, M., Nasir, J., Obaid, M., Pelachaud, C., Peters, C. (2020). Engagement in human-agent interaction: an overview.** *Frontiers in Robotics and AI* 7:92. https://doi.org/10.3389/frobt.2020.00092
  An overview of the different meanings of "engagement" (task vs social, children vs adults, lab vs long-term), with detection and generation models. Use it to define your funnel stages.

- **Vázquez, M., Carter, E. J., McDorman, B., Forlizzi, J., Steinfeld, A., Hudson, S. E. (2017). Towards robot autonomy in group conversations: understanding the effects of body orientation and gaze.** *HRI 2017*. https://doi.org/10.1145/2909824.3020207
  A 2×2 experiment on robot orientation and gaze in group conversation. Gaze and body motion change how each other is perceived, so they should be designed together. This matters for a G1 that cannot turn its body.

- **Mumm, J., Mutlu, B. (2011). Human-robot proxemics: physical and psychological distancing in human-robot interaction.** *HRI 2011*. https://doi.org/10.1145/1957656.1957786
  Participants who disliked the robot kept further away when it gazed at them, and disclosed less. Likeability and gaze together shape comfortable distance.

- **Bergström, N., Kanda, T., Miyashita, T., Ishiguro, H., Hagita, N. (2008). Modeling of natural human-robot encounters.** *IROS 2008*. https://doi.org/10.1109/IROS.2008.4650896
  Laser tracking classified passers-by by interest level. An actively engaging robot and a passively acknowledging one were rated equally natural, while random gestures were rated much less natural.

## 4. LLM-based and speech-to-speech social robots (2023–2026)

- **Zhang, C., Chen, J., Li, J., Peng, Y., Mao, Z. (2023). Large language models for human–robot interaction: A review.** *Biomimetic Intelligence and Robotics* 3(4), 100131. https://doi.org/10.1016/j.birob.2023.100131
  A review of LLMs in HRI covering multimodal input, reasoning and planning. It flags contextual understanding, data privacy and ethics as open challenges.

- ★ **Kim, C. Y., Lee, C. P., Mutlu, B. (2024). Understanding Large-Language Model (LLM)-powered Human-Robot Interaction.** *HRI 2024*. https://doi.org/10.1145/3610977.3634966
  A study (n=32) compared an LLM-powered robot with text and voice agents. Embodiment raised expectations for nonverbal cues and helped connection-building, but the robot was weaker at logical communication and could induce anxiety.

- ★ **Williams, T., Matuszek, C., Mead, R., DePalma, N. (2024). Scarecrows in Oz: The use of large language models in HRI.** *ACM THRI* 13(1). https://doi.org/10.1145/3606261
  The authors frame LLMs as "Scarecrows": black-box placeholder modules, like Wizard-of-Oz. They propose reporting guidelines.
  - Follow-up: **Matuszek, C., Williams, T., DePalma, N., Mead, R., Wen, R., Schneiders, E. (2025/26). Reporting Guidelines for Large Language Models in Human–Robot Interaction.** *ACM THRI*. https://doi.org/10.1145/3777552. Concrete guidelines on what to report when HRI studies use LLMs; you should follow these for gpt-realtime.

- ★ **Irfan, B., Kuoppamäki, S., Hosseini, A., Skantze, G. (2025). Between reality and delusion: challenges of applying large language models to companion robots for open-domain dialogues with older adults.** *Autonomous Robots* 49. https://doi.org/10.1007/s10514-025-10190-y
  The work used a Furhat with GPT-3.5: first 6 older adults, then co-design workshops with 28. Early versions interrupted users, responded slowly and repetitively, and stayed superficial. Later versions were smoother, but hallucinations, outdated information and missed disengagement cues caused frustration.

- **Cherakara, N., Varghese, F., Shabana, S., Nelson, N., Karukayil, A., Kulothungan, R., et al. (2023). FurChat: An embodied conversational agent using LLMs, combining open and closed-domain dialogue with facial expressions.** *SIGDIAL 2023 (demo)*. https://doi.org/10.18653/v1/2023.sigdial-1.55
  A GPT-3.5 Furhat receptionist for visitors at the National Robotarium (Edinburgh) that mixes facility information with open chat and generated facial expressions. It is a system demo with no field evaluation.

- ★ **Herath, D. C., Busby Grant, J., Rodriguez, A., Davis, J. L. (2025). First impressions of a humanoid social robot with natural language capabilities.** *Scientific Reports* 15, 19715. https://doi.org/10.1038/s41598-025-04274-z
  A ChatGPT-equipped Pepper was taken to a public innovation festival, and attendees (n=88) gave feedback after a short interaction. Responses were emotionally mixed, attended to the robot's body and movement, carried expectations about interaction rituals, and raised diversity and inclusion. Talking too much or missing cues caused dissatisfaction. (One press article wrongly says it appeared in *Nature*.)

- ★ **Heisler, M., Becker-Asano, C. (2025). Conversations with Andrea: Visitors' opinions on android robots in a museum.** *RO-MAN 2025*. https://doi.org/10.1109/RO-MAN63969.2025.11217762
  An LLM-driven android talked fully autonomously with uninformed museum visitors for six days, with 44 interviews and 4,436 logged requests. Perception was positive overall, and changing the gender cues did not change it. Visitors most wanted more languages and **faster responses**.

- **Garello, L., Cocchella, F., Sciutti, A., Catalano, M., Rea, F. (2025). Next-Gen Museum Guides: Autonomous navigation and visitor interaction with an agentic robot.** arXiv:2507.12273. https://arxiv.org/abs/2507.12273
  An LLM-based Q&A museum guide (Alter-Ego) was tested with 34 participants in a real museum. It was generally well received, but had limits in comprehension and responsiveness. (Preprint.)

- **Müller, A., Jeschke, S., Richert, A. (2025). Are we generalizing from the exception? An in-the-wild study on group-sensitive conversation design in human-agent interactions.** *RO-MAN 2025*. https://doi.org/10.1109/RO-MAN63969.2025.11217533
  A Furhat and a virtual MetaHuman, both with a hybrid retrieval and generative back end, were run with N=188 museum visitors, many of them in groups. Group-adapted wording did not significantly improve satisfaction. This is relevant because Open Day visitors arrive in families and groups.

- **Skantze, G. (2021). Turn-taking in conversational systems and human-robot interaction: A review.** *Computer Speech & Language* 67, 101178. https://doi.org/10.1016/j.csl.2020.101178
  A review of turn-taking cues and models. Robots and voice assistants still suffer from interruptions and long response delays.

- ★ **Skantze, G., Irfan, B. (2025). Applying general turn-taking models to conversational human-robot interaction.** *HRI 2025*. https://doi.org/10.1109/HRI61500.2025.10973958
  Voice Activity Projection (VAP) and TurnGPT were used on a Furhat with an LLM, in a within-subjects study (N=39). Participants preferred it, and it reduced response delays and interruptions compared with a silence-threshold baseline.

- ★ **Inoue, K., Okafuji, Y., Baba, J., Ohira, Y., Hyodo, K., Kawahara, T. (2025). A noise-robust turn-taking system for real-world dialogue robots: A field experiment.** *IROS 2025* (accepted; arXiv:2503.06241). https://arxiv.org/abs/2503.06241
  A noise-robust VAP model was compared with cloud speech recognition in a **shopping-mall field experiment**. Response latency dropped significantly, and faster responses improved the experience. This is the best field evidence that latency matters in public settings.

- ★ **Fu, M., Shi, Z., Huang, M., Liu, S., Kian, M., Song, Y., et al. (2025). Personalized socially assistive robots with end-to-end speech-language models for well-being support.** arXiv:2507.14412. https://arxiv.org/abs/2507.14412
  An end-to-end speech-language model was put on the Blossom robot, in a small within-subjects lab study with students (N=11). The full text confirms the model was **GPT-4o-realtime via OpenAI's Realtime API**, the same model family you are using. Participants found turn-taking, back-channelling and empathy natural, but the robot's movements lacked variety and synchronisation, and its replies felt generic and repetitive. This is the closest prior robot study with your model, but it ran in a lab, not a crowd. (Preprint.)

- ★ **Studerus, E., Zhong, V. J., Vonschallen, S. (2026). A framework for low-latency, LLM-driven multimodal interaction on the Pepper robot.** *HRI 2026 (LBR)*. https://doi.org/10.1145/3757279.3788808 (arXiv:2603.21013)
  An open-source Pepper framework replaces the STT→LLM→TTS cascade with end-to-end **speech-to-speech** models, for lower latency and preserved paralinguistic cues. It adds function calling for gaze, navigation and multimodal feedback. It is a system paper with no user study.

- ★ **Abbo, G. A., Belpaeme, T. (2025). I was blind but now I see: Implementing vision-enabled dialogue in social robots.** *HRI 2025*, pp. 1176–1180. https://doi.org/10.1109/HRI61500.2025.10973830
  A dialogue manager feeds live camera frames (with summarisation) into GPT-4 or IDEFICS on a Furhat, demonstrated in six interactions. This is the closest prior "LLM sees the user and talks about it" system, but it is not a field study.

- **Mauliana, M., Ashok, A., Czernochowski, D., Berns, K. (2025). Exploring LLM-powered multi-session human-robot interactions with university students.** *Frontiers in Robotics and AI*. https://doi.org/10.3389/frobt.2025.1585589
  A Flan-T5 humanoid (EMAH, not Ameca as one search summary claimed) held four sessions with 13 students. Conversation length and turn-taking dropped mid-study, matching slower generation and speech-recognition errors.

- **Bu, F., Tsai, M., Tjokro, A., Bhattacharjee, T., Ortiz, J., Ju, W. (2025). Using vision-language models as proxies for social intelligence in human-robot interaction.** arXiv:2512.07177. https://arxiv.org/abs/2512.07177
  A five-day Wizard-of-Oz deployment in a university café showed how people signal readiness to interact. The authors propose cheap gaze and proxemics detectors that trigger VLM queries about whether to engage, evaluated on replayed field data. (Preprint.)

## 5. Open days, campus deployments, randomised in-the-wild designs, teenagers

- ★ **Schiffmann, M., Struth, F., Jeschke, S., Richert, A. (2025). When to say "Hi" – Learn to open a conversation with an in-the-wild dataset.** *RO-MAN 2025*. https://doi.org/10.1109/RO-MAN63969.2025.11217902 (arXiv:2512.03991)
  **This is the closest prior work to your "robot speaks first vs waits" manipulation.**
  - **Setup:** a stationary Furhat information point at the Deutsches Museum Bonn, with intent-based NLU plus a local Llama 3 fallback.
  - **Randomisation:** the full text says that, for each detected user, the system chose at random whether the robot greeted first or started in listen mode for the user to speak first.
  - **Data and purpose:** N=201 single-user interactions, used to train a classifier for greeting timing and opener.
  - **Consent:** visitors pressed a buzzer to consent before entering the interaction area.
  - **Differences from your study:** the randomisation served data collection, not an outcome comparison, and there was no personalised opener.
  - Companion paper from the same deployment: Schiffmann, Jeschke & Richert (2025), *Classification of user satisfaction in HRI with social signals in the wild*, ICSR+AI 2025, arXiv:2512.03945, https://arxiv.org/abs/2512.03945. It classifies satisfaction automatically from pose, face and distance (46 interactions).

- ★ **Okafuji, Y., Ozaki, Y., Baba, J., Nakanishi, J., Ogawa, K., Yoshikawa, Y. (2022). Behavioral assessment of a humanoid robot when attracting pedestrians in a mall.** *International Journal of Social Robotics*. https://doi.org/10.1007/s12369-022-00907-9
  Three autonomous behaviours (greeting, in-trouble, dancing) were compared, along with human advertisers, on two outcomes: whether pedestrians stop, and how long they stay. "In-trouble" made people stop more and stay longer, and greeting and dancing matched human advertisers.
  - Note the sample-size discrepancy: the journal abstract says 5,000+ pedestrians, while the earlier HRI 2020 LBR ("Please listen to me", https://doi.org/10.1145/3371382.3378289) and arXiv:2109.02771 say 65,000+. Check the full text before quoting a number.
  - This is the main precedent for large-N, automatically measured stop and stay outcomes.

- ★ **Shi, C., Satake, S., Kanda, T., Ishiguro, H. (2018). A robot that distributes flyers to pedestrians in a shopping mall.** *International Journal of Social Robotics* 10(4), 421–437. https://doi.org/10.1007/s12369-017-0442-7
  Successful human distributors approach from the front and extend the arm only near the target. Pedestrians were more likely to accept a flyer if previous pedestrians had. A robot model built on this was confirmed in a field experiment. Acceptance is a direct analogue of your "accepted" stage, and the social-proof effect will matter at a busy Open Day stand. (Abstract content checked via search snippets.)

- ★ **Blair, A., Foster, M. E. (2023). Real-world evaluation of a university guidance and information robot.** *ICSR 2023, LNCS 14454*, pp. 193–203. https://doi.org/10.1007/978-981-99-8718-4_17
  A Pepper supported help staff in a new University of Glasgow teaching building for a supervised one-week deployment, with questionnaires from 59 students and staff. Reactions were generally positive but varied widely, and the paper lists the barriers to unsupervised deployment.

- ★ **Holthaus, P. (2023). Interactive robots as inclusive tools to increase diversity in higher education.** arXiv:2303.01316. https://arxiv.org/abs/2303.01316
  The only item found that is explicitly about **university open days**. It reflects on two University of Hertfordshire outreach events and proposes robot activities for open days to attract under-represented prospective students. It is a position or experience paper, not a controlled study.

- **Björling, E. A., Thomas, K., Rose, E. J., Cakmak, M. (2020). Exploring teens as robot operators, users and witnesses in the wild.** *Frontiers in Robotics and AI* 7:5. https://doi.org/10.3389/frobt.2020.00005
  Teens (n=62) took part in schools through a Participatory Wizard-of-Oz method. Negative attitudes toward robots dropped after interaction, with themes of authenticity, empathy, emotional engagement and "imperfection creates connection". This is relevant because your audience is mostly 16–18-year-olds and their parents.

---

## Could not verify / not found / cautions

- **Peer-reviewed field studies of Unitree G1 (or Ameca) as a conversational greeter:** none found. The arXiv G1 papers from 2025–26 that I found are about control, manipulation and simulation.
- **Field studies of gpt-realtime or GPT-4o-realtime (speech-to-speech) on a robot in public:** none found. The nearest are Fu et al. 2025 (lab, N=11) and Studerus et al. 2026 (system paper).
- **Studies where a robot comments on a stranger's clothing or appearance and creepiness or privacy reactions are measured:** none found. Glas et al. 2017 (personal greetings, for example a new hairstyle) is the nearest.
- **Hall (1966), *The Hidden Dimension* (proxemics book):** not checked, since it has no DOI. Cite it from the book itself if needed.
- **Directions robot:** ACM's own pseudo-DOI 10.5555/2615731.2615835 does **not** resolve at doi.org. Use https://doi.org/10.65109/kapi6982.
- **Abstracts not retrievable from the publisher (only metadata verified):**
  - Foster et al. 2016 (MuMMER, LNCS)
  - Jung & Hinds 2018 (editorial)
  - Glas et al. 2017, Shi et al. 2018 and Liu et al. 2018: summaries rely on search-engine snippets of the publisher abstract. Re-read these before quoting.
- **Okafuji et al.:** the participant count differs between versions (5,000+ vs 65,000+).

---

## Synthesis

### What is already well established
1. **Most passers-by do not engage, and interactions are short.** Valerie's interactions rarely passed 30 s (Gockley 2005). People often fail to notice that a robot is addressing them, or are unsure it means them (Satake 2009). Robot utterances are often not remembered even when the robot is noticed (Saad 2019). Children cluster once others are already interacting (Aaltonen 2017), and social proof affects acceptance (Shi 2018).
2. **How and when the robot opens matters.**
   - The opening is a stepwise, contingent process (Pitsch 2009; Gehle 2017).
   - Both blanket proactivity and pure passivity are suboptimal (Kato 2015).
   - Active and passive acknowledgement can look equally natural (Bergström 2008).
   - A verbal greeting raises attention and friendliness but not compliance (Fischer 2014).
   - Unusual behaviours ("in trouble") stop more pedestrians than a plain greeting (Okafuji 2022).
3. **Engagement can be sensed from position, orientation and head pose.** This is mature, and simple rule-based detectors hold up well against learned ones in the field (Michalowski 2006; Bohus & Horvitz 2009; Foster et al. 2017; Oertel 2020).
4. **Personalisation and praise work.** Personalised service raises rapport and engagement (Lee 2012). Observation-based personal greetings are appreciated (Glas 2017). Flattery from machines is effective even when people know it is noncontingent (Fogg & Nass 1997; Kaptein 2010), and people may accept flattery from robots more readily than from humans (Chai 2026).
5. **LLM robots are now in public venues** (Herath 2025; Heisler 2025; Garello 2025; Müller 2025). The recurring problems:
   - **Latency and turn-taking** (Irfan 2025; Heisler 2025; Mauliana 2025; Skantze 2021).
   - Talking too much.
   - Hallucination.
   - Language coverage.

   Better turn-taking measurably cuts delays, including in a mall field test (Skantze & Irfan 2025; Inoue 2025). Speech-to-speech models are proposed as the fix (Studerus 2026; Fu 2025), but they have not been field-tested.

### Gaps this project can fill (honest about near-misses)
1. **A randomised, per-visitor comparison of openers, with outcomes, in a real crowd.** Closest: Schiffmann et al. 2025, who randomised robot-greets-first vs listen-first for each visitor. Their randomisation fed a timing classifier, not a comparison of acceptance or conversation outcomes, and was gated by a consent buzzer. Okafuji 2022 and Saad 2019 compared opening behaviours with passers-by, but not the wording of verbal openers. A factorial manipulation with these outcomes appears new:
   - **Opener type:** personalised (names clothing) vs generic.
   - **Initiative:** robot speaks first vs waits.
   - **Outcomes:** acceptance (stepped onto the spot or replied) and conversation depth.
2. **Vision-grounded, LLM-generated personalised openers that refer to a stranger's appearance.** Glas 2017 commented on observed novelty (for example a hairstyle) for repeat customers, using a teleoperated robot. Abbo & Belpaeme 2025 showed a vision-LLM dialogue in six lab interactions. Nobody appears to have tested, in the wild, whether "naming what you are wearing" raises uptake, or whether some people find it creepy or a privacy intrusion (Lutz & Tamò-Larrieux 2020; Rueben 2018). A short exit question on comfort would turn this into a contribution rather than a confound.
3. **Full-funnel metrics logged automatically from detection to goodbye.** Prior field work reports either top-of-funnel attention or stopping (Hayashi 2007; Saad 2019; Okafuji 2022) or the quality of conversations with participants who opted in (Herath 2025; Heisler 2025). Few report stage-by-stage conversion (noticed → invited → accepted → turns and duration → goodbye vs drop-off) with LLM dialogue in one pipeline. The UE-HRI dataset (Ben-Youssef 2017) and the forecast-based disengagement work of Bohus & Horvitz (2014) are useful anchors for the drop-off stage.
4. **The first field use of a speech-to-speech LLM (audio in, audio out, with frames) on an embodied robot.** Evidence so far comes from lab studies or system papers (Fu 2025; Studerus 2026). Field studies show latency hurts (Inoue 2025; Heisler 2025). Logging response latency, barge-ins and overlaps per turn would give the first in-the-wild numbers for S2S.
5. **A stationary humanoid at a university Open Day with prospective students and parents.**
   - Open-day evidence is anecdotal (Holthaus 2023).
   - Campus robots have targeted current students and staff (Blair & Foster 2023; Saad 2019).
   - Teen-robot work is school-based (Björling 2020).
   - No peer-reviewed social-HRI field study of a Unitree G1 turned up.

   A full-size humanoid that does not move or gesture also isolates the effect of speech, because nonverbal approach behaviour (central to Satake 2009, Kato 2015 and Shi 2018) is absent by design. That should be framed as a deliberate constraint.

### Design cautions surfaced by the literature
- **Selection bias:** targeting only people wearing green will skew the sample, so report it, or randomise who is targeted.
- **Social proof:** Shi 2018 and Aaltonen 2017 show that crowds make others more likely to join, so log group size and whether someone was already at the robot as covariates. Treat clusters, not individuals, as the unit where needed.
- **Consent and privacy:** cameras plus personal comments raise these issues. Schiffmann 2025 used a consent buzzer, which changes how the opening unfolds, so decide and report your consent model explicitly.
- **LLM reporting:** follow Matuszek et al.'s guidelines. Report the model version, prompts, latency and guardrails.
