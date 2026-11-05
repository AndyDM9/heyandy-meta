# The form's answers, as sent

The form (read November 4) has three required answers of at most 3,000 characters each, and no field for the project's
name or the live demo, so the first answer carries both. It turns anything shaped like a web address into a link, so file
names are written out in words here. These are `docs/submission.md` cut to fit: a test checks each answer's length, that
no file name became a link, and that every figure here is in the documents or the result it comes from.

## Project Description

Andy, by HeyAndy: a tabletop robot that finds what you've lost, points at it, and keeps your home's pictures in your home. Every model it runs is Meta's.

"Hey Andy, where are my glasses?" Andy turns to your voice and looks around, the TV showing each view with SAM 3.1's outlines. As it points and its own camera checks the point, it says "There they are! To my left, about 5 feet away." Ask for "the red cup" with only a blue one there: after a fix, no point, 4 of 4 on the robot.

Public demo, no robot needed (drawn sample scenes, two models live in your browser): https://huggingface.co/spaces/heyandy-ai/andy

FROM BEFORE THE EVENT: a Reachy Mini Lite with its maker's open-source software; our own earlier object-finding prototype; the HeyAndy name and logo; HeyAndy, Inc.'s separate product in development; an October 24 repository skeleton (only its licence text is here). No code from the prototype or the product is here. All else, apart from open-source pieces the README lists, was built during the event.

THE PROBLEM: Three in four adults 50 and older want to stay in their homes as they age (AARP, 2024), and a quarter of Americans 65 and older live alone (Pew Research, 2025): when the glasses go missing, there's no one to ask. A tracker finds only what you tagged.

WHAT ELSE IT DOES
- "I fell and I can't get up": "If you need help, please call 911 right away. I'll find your phone." It can't call anyone; it searches for the phone and points.
- 15 languages. Called in another, in Andy's synthetic voice, it switched 31 times in 42, never to a wrong one.
- A missed search becomes a promise: when it turns up, Andy points and says so, unprompted.
- Unplug the network and Andy carries on. Each turn, the TV shows a privacy receipt: which words went to which cloud model, or "Nothing left this house".

MEASURED
- On the robot, judged once by our founder, before the final fixes (three things, five places each, or hidden): 13 of 15 right, never a wrong point.
- On the robot, alone, nobody checking what it pointed at: 250 of 253 searches ended in a point. On the final code: a median 1.1 degrees off the middle of its camera's view, 2.2 at worst, 7.8 s for the search alone.
Results, failures included: evals/results and docs/research in the repo.

NO HEALTH ADVICE: Andy is built to give no medical, medication or mental-health advice. A health question the rule catches (25 of 34 held out) gets Andy's own fixed words, and no model answers it. The rest reach a model told never to advise: of 26 such answers, Muse Glimmer judged one advice, we read a few more as health information, and no clinician has read them. Limits: the repository's system card.

WHAT'S NEXT: Andy Finder offers the find to Reachy Mini owners with a Model API key and no GPU (recorded runs so far used our GPU): https://huggingface.co/spaces/andydm/andy-finder (its pictures go to the API: for rooms you're happy to share). Next: homes with the people it's for, then one box instead of two GPUs.

## Describe your use of Meta products to build the submitted project

Every model Andy runs is Meta's: nine open-weight models on our own two GPUs beside the robot, and Muse Spark and Muse Image through Meta's Model API.

ON OUR OWN GPUS
- SAM 3.1: finds things and the person. Object Multiplex tracks every cup at once (made-up shuffles so far).
- Muse Glimmer 30B: conversation, plans searches offline, checks pictures, translates Andy's 14 other languages.
- MapAnything: how far a found thing is; the room in 3D from five looks.
- V-JEPA 2: meant to notice a watched thing put down or picked up (tried only on empty clips).
- Omnilingual ASR hears the person. SeamlessM4T v2 is Andy's voice, because Meta's API has no text-to-speech.
- DINOv2: knows the person's own things by sight (not yet tried with two real mugs).
- Llama Guard 3 8B: a second crisis check, and it reads a model's conversation, web and agent answers for health advice.
- Llama Prompt Guard 2: reads each web page before Muse Spark's computer use sees it.

THROUGH THE MODEL API
- Muse Spark 1.3: plans searches and multi-part requests, web answers, computer use. It gets words, and screenshots of web pages you ask to see.
- Muse Image 1.0: pictures and the map of your things, from words only.

IN THE VISITOR'S BROWSER (public demo; nothing leaves it)
- wav2vec 2.0 hears you, and DINOv2 finds your own things (not yet on a real phone).

BEYOND A BASIC INTEGRATION
- A point checked by its own camera. The camera showed the head sagging after its pointing nod and the base's turn being added twice; now each pixel gets its true ray and the head is read back. Earlier runs reached 7.8 degrees off the middle of the view on keys; on the final code, over 18 searches, a median 1.1, 2.2 at worst.
- Told where, Glimmer plans. On the same 20 simulated rooms (picture checks stood in for): told "behind you", 4.6 looks against a fixed sweep's 7.0, slower overall (20.5 s against 13.9 s); with look-alikes described, both got 18 of 20.
- Agents that can't move the robot by themselves: named views and numbered places, never motor values, a search's arguments checked in code. On 12 multi-part requests in a simulated room, real models planning, after fixes on those 12: Muse Spark 12 of 12, Glimmer offline 12 of 12.
- Notes in view. A drawn note made Glimmer answer "BANANA BANANA". Now it's told writing is never an instruction, and a note addressed to Andy isn't read out: 9 of 54 drawn notes got through, now 0 of 72, held-out sets included.
- The TV shows a find's model calls live and times each turn. The timing showed the answer waiting for the point, so Andy now answers while pointing, 9.6 s sooner on the same first-turn search.
- Open weights verified: 54 of 54 files are byte for byte what Meta published (Llama Guard 3 as our own GGUF). Sources and licences: https://github.com/AndyDM9/heyandy-meta/blob/main/docs/open-weights.md

WHAT META'S MODELS TAUGHT US
- Asked for "keys", SAM 3.1 outlined every key of a keyboard (28 of 28 masks), so Andy asks for "bunch of keys".

## Why are Meta's models important to your solution?

Andy's promise is that a home's pictures and voice stay in the home. Meta's open weights are what make that promise possible: seeing, measuring, hearing, thinking, speaking and guarding can all run on the computer beside the robot, with no inference provider.

PRIVACY. The camera and microphone reach only models on that computer. Muse Spark and Muse Image get words, plus screenshots of web pages you ask to see, and the TV's receipt shows what went; on hackathon credits, Meta may use that content for product improvement. In a privacy audit (a day of 21 requests in a simulated room, with the real cloud models and every request from Andy's Python code recorded), no camera picture reached the cloud (24 taken), 40 of 43 pieces sent were on the receipt word for word (the other 3 inside Andy's own instructions), and its one crisis sentence reached no model. Two exceptions: a switch for filming a staged room sends frames to SAM 3.1 through the API, and the TV says so; and until November 3 the robot's stream server listened on the home network, registered with its maker's relay. Its log shows no stream opened since October 30; now it's on this computer only.

A NEW PHYSICAL ABILITY. SAM 3.1's outline of your glasses is what becomes a point in the room. MapAnything measures how far away they are. DINOv2 reads the thing's own pixels inside SAM 3.1's mask to know your mug by sight (not yet tried with two real mugs). Together they give a small robot with no wheels and no arm a camera that looks round the room and a point it checks itself: a median 1.1 degrees off on the final code.

IT KEEPS WORKING OFFLINE. Muse Glimmer plans searches and multi-part requests on our own GPU: 12 of 12 offline in a simulated room, level with Muse Spark's 12 of 12, after fixes on those requests. Online, Muse Spark adds web answers and computer use.

LANGUAGES. Omnilingual ASR hears, Muse Glimmer translates on the computer beside the robot, and SeamlessM4T v2 speaks, in 15 languages. After fixes on these sets, written requests reach the right ability: Spanish 41 of 41, 13 more 104 of 104. In Andy's synthetic voice, fed straight to the recogniser: 36 of 41 and 89 of 104. Not yet with native speakers.

SAFETY. Llama Guard 3 reads what the person says before any other model, and reads a model's conversation, web and agent answers before Andy says them. Crisis words in any of its 15 languages get the 988 line from code.

A PATH TO PEOPLE'S HOMES. Open weights let us measure what one home box would need. At rest Andy holds 40.5 GB of GPU memory: the language model (Muse Glimmer) is 17.6 GB and everything else 22.9 GB, under one 24 GB card. Next is one box, with smaller language and guard models, and a voice licensed for a product (SeamlessM4T v2 is CC-BY-NC). Meanwhile SAM 3.1 through the Model API offers the find to Reachy Mini owners with a key and no GPU: two pictures when it's in the first view (about half a cent at Meta's $2.50 per 1,000 images), seven at most.
