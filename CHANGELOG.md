# Changelog

## 2026-11-24
- **Easier first run (viewer feedback):** a small *Quick start* strip (paste a link, pick Fast, press Make clips) with one *Got it* button; the red **FFmpeg** chip now installs FFmpeg for you when you click it; the disk chip opens Storage; Make clips frees old partial downloads automatically when the disk is getting full and says so plainly if it is almost full; common failures (private video, removed video, age-restricted, blocked in your country, no internet, disk full, FFmpeg missing, wrong kind of link) now explain themselves in simple English with a short Hinglish line instead of a long technical message.
- **A time you give now cuts exactly that clip.** Type only a time in the focus box (`1:35:00`, `1:35:00 to 1:36:00`, `5700s`, `1h35m`, `minute 95`) and that clip is made: a range as written, a single time from that second for the usual clip length, ending when the sentence ends. Add words (funny, chase) and the times stay hints. **Only a part of the video (From/To)** is now also used by **Make clips** (before, only Get preview used it, so From/To was ignored when you pressed Make clips directly): up to 3 minutes gives that exact clip, a longer part gives clips found inside it. `1h35m` and `1 hour 35 min` were read as two different times; fixed.
- **Fast mode on very long videos:** reading a finished stream's chat no longer holds everything up (Fast waits at most 20 s for it; Balanced and Best wait longer). A 3.4 hour stream gave 3 clips in 4.3 minutes (before, the chat download alone could run 10+ minutes).
- **Titles and hooks:** clips no longer all get the same title, and a hook that has to be taken from the transcript is the real quote, without a made-up lead-in.
- **Automation (Settings, new tab):** a **watch folder** (drop a finished recording in it and clips are made by themselves, even overnight), a **webhook** that announces each finished clip (title, hook, score, hashtags; never the video), and **words to avoid**: a clip whose title, hook, description or captions contain one gets a red 'Check before posting' tag.
- **Viral score is back on every card**, with the four parts (Hook, Engagement, Value, Share) as small bars and a Ready to post / Review first badge, also in My clips (old clips get it rebuilt from their saved signals).
- **Fast mode is quicker again:** it reads moments with the lighter local model (llama3.2) and skips a second AI call for the opening heading when the first one already has a quote behind it; the bigger model is used in Balanced and Best. A 1h43m video gave 2 clips in about 2 minutes (was 3.5).
- **Editor effects:** mute or bleep selected transcript words, add a facecam bar or blur during censored words, and add a playback progress strip to the export.
- **Editing tracks:** download a Premiere Pro / DaVinci Resolve XML package from a saved facecam clip. Gameplay and transparent facecam are separate media tracks, with SRT included when available.
- **Live clipping:** optionally make a clip at an interval as well as on chat spikes. The chat signal now counts distinct authors and shows the dominant reaction for a spike.
- **Activity:** see which stage is running for source preparation, moment finding, captions and export.
- **Clip Editor:** grey timeline areas show available source before and after the cut. Drag the edges to recover context, use Set in/Set out, or cut a spoken word from the video through the transcript. New audio-first clips keep up to 15 seconds of source on either side.
- **Creators:** manage auto-clipping from its own sidebar tab. Saved YouTube channels also appear in the YouTube feed, and you can save a channel from its video or live card.
- **YouTube:** see which gaming creators are live and browse recent uploads and replays. Sort by newest or by views per day, or send a video link straight to the clipping workspace.
- **Campaigns:** browse open Content Rewards deals with their original posters, USD rates and prize pools. Affiliate links are available for Content Rewards, Clipster and 100x Clipping.
- **Results:** see where clips land in the source, filter Ready and Review, and recover moments skipped for frozen frames.
- **Editor:** export a reaction GIF, place timed bass hits, sweeps or flashes, enable a loop ending and reuse saved caption profiles.
- **Posting:** save drafts to review before scheduling, with configurable daily caps and spacing.
- **Hindi is always written in Hinglish** (Roman letters) in captions, hooks and titles, even when YouTube gives Hindi script or another caption language was picked. Only the हिंदी option keeps Devanagari. Spelling is chat-style: "ja raha hoon", "saccha", "shayad", "order" (not jaa, sachcha, shaayad, aardar).
- **Your words:** change a word in the editor's transcript and press **Always fix**; every new clip spells it right from then on (names like Andy, English words said in a Hindi accent). Add or remove words in the editor under *Your words*. Works on YouTube captions and the speech model, before and after Hinglish, and keeps word timings.
- **8 new caption styles** (Karaoke is the new default, TikTok, Pill, One word, Cinematic, Boxed, Outlined, Comic).
- **English words stay English in Hinglish captions:** police, phone, game, car... are no longer written as pulis, fon, gem (loanword list in loanwords.py, Hindi endings like -wale handled).
- **Clips can be deleted easily:** trash button on every card, Select mode in My clips, optional source-video delete. Edit clip opens the frame area again. The facecam is found and selected automatically for a fresh video, and your choices are remembered.
- **Simpler first screen:** one link box and Make clips, a one-line summary of what will happen, and a single Advanced button that opens tabs (Clip options, Frame and layout, Captions, Transcript and review, Style extras, Streams and tools). Nothing was removed.
- **Activity:** running and waiting jobs with progress, Cancel and Retry, plus 'Add to queue instead'.
- **Result cards** have a score ring and the reason; status messages show under the link box.
- **Storage** (left side): used and free space, one-click clean-up of temporary files, live recordings and unused sources, delete old clips, and choose another folder for BloomClipping's files. Supporters is a small toggle.
- Also shipped from the earlier ChatGPT session: batch resume, timeline studio, series/topic/recap/trailer workflows, local MCP, direct YouTube/Instagram/TikTok publishing.

## 2026-11-23
- **Facecam:** the automatic facecam search is now on by default for Make clips. If no webcam is found and you did not draw boxes, the clip uses the full-frame blur layout instead of an empty or wrong box.
- **Stuck downloads fixed at the root:** FFmpeg downloads give up after 30 s without data, a part cut from a long video shows live progress, short videos and big parts are downloaded whole (about 8x faster than FFmpeg cutting) and cut afterwards, the speech model download says clearly when there is no internet, an empty audio file is retried with other formats, and a section that FFmpeg cannot fetch falls back to a single-file stream.
- Videos over 2 hours always use the audio-first mode, even in Deep mode.

## 2026-11-22
- **Cloud AI (optional, off by default):** use Groq, OpenRouter, Gemini, OpenAI or LM Studio for moment scoring, titles and hooks on a slow PC. Only clip text is sent; the key stays in `data/llm.json`. Test connection button included.
- **Heading looks:** new default **Impact** (big bold text, one accent word, pop-in, pink underline), plus **Neon glow**, **Banner bar** and the classic box. Boxes now have rounded corners.
- **Sharper hooks and titles:** the local model is asked for scroll-stopping formulas (curiosity gap, hot take, mistake warning, secret, reaction), still grounded in what is really said in the clip; the no-model fallback is punchier.
- **Cover image** for every clip (`Cover image` link, also inside the clips ZIP).
- **System check line** at the top: FFmpeg, encoder, YouTube runtime, AI model, disk, each with a fix when red.
- **Fixes:** macOS caption filter, blocked PyAV (Windows Smart App Control), bad caption times no longer fail a clip, clearer "app closed" message.
- **New:** YouTube browser-login setting for the bot check, optional From/To part import, 480p/360p data-saver qualities, Facecam look sliders, fade in/out, AMD/Intel GPU encoders, opening-heading on/off.

## 2026-11-21
- 1080p default with a 4K option beside Get preview (no more silent 720p), videos over 2 hours are imported by part, in-app updater, donate bar and supporters list, Report a problem, stuck-job watchdog, PyAV 19 fix, portable FFmpeg fallback, Windows installer uses Python 3.10 to 3.13.
