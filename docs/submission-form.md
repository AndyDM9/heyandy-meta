# The form's answers, as sent

The form (read November 4) has three required answers of at most 3,000 characters each, and no field for the project's
name or the live demo, so the first answer carries both. These are `docs/submission.md` cut to fit: a test checks each
answer's length and that every figure here is in `docs/submission.md` or `docs/open-weights.md`.

## Project Description

Andy, by HeyAndy: a tabletop robot that finds what you've lost, points at it, and keeps your home's pictures in your home. Every model it runs is Meta's.

"Hey Andy, where are my glasses?" Andy turns to your voice and looks around, the TV showing each view with SAM 3.1's outlines. It points, checks with its own camera that the point landed, and says "There they are! To my left, about 5 feet away." It skips a picture of glasses on the TV, and picks "the blue cup" from look-alikes.

Live demo, no robot needed: https://huggingface.co/spaces/heyandy-ai/andy

FROM BEFORE THE EVENT: a Reachy Mini Lite robot with its maker's open-source software, our own earlier object-finding prototype (none of its code is in the repository), the HeyAndy name and logo, and an October 24 skeleton of a repository, of which only the licence text is here. Everything else here was built during the event, on Meta's models.

THE PROBLEM: Three in four adults 50 and older want to stay in their own homes as they age (AARP, 2024), and a quarter of Americans 65 and older live alone (Pew Research, 2025): when the glasses go missing, there's no one to ask. A phone app can't look for them, and a camera that streams the living room to the cloud is a camera most people won't have.

WHAT ELSE IT DOES
- "I fell and I can't get up": "If you need help, please call 911 right away. I'll find your phone." It can't call anyone, but it searches for the phone and points at it.
- 15 languages, and it notices which one you called it in.
- It remembers what you tell it. A missed search becomes a promise: when the thing turns up, Andy points and says so, unprompted.
- Several requests at once, reminders in person, and the weather radar on the TV.
- Unplug the network and Andy carries on. Every turn, the TV shows a privacy receipt: exactly which words went to which cloud model, or "Nothing left this house".

MEASURED
- On the robot, judged by a person (three things, five places each on our desk, or hidden): 13 of 15 right, never a wrong point.
- Alone in the room, its own camera judging: 250 of 253 unattended searches ended in a point. On the final code: a median 1.1 degrees off, 2.2 at worst, 7.8 s a find from a typed request.
- Privacy audit, a day of 21 requests with the real models: no camera picture reached the cloud.
Every result, failures included, is in evals/results/ and docs/research.md.

NO HEALTH ADVICE: Andy gives no medical, medication or mental-health advice, interpretations or recommendations. A health question gets Andy's own words, written by hand in each language, and no model answers it. Its limits are published in docs/system-card.md.

WHAT'S NEXT: Andy Finder brings the find to anyone with a Reachy Mini, no GPU, through Meta's Model API: https://huggingface.co/spaces/andydm/andy-finder (its pictures go to the API, so it's for rooms you're happy to share). For the whole Andy: homes with the people it's for, then one box instead of two GPUs.

## Describe your use of Meta products to build the submitted project

Every model Andy runs is Meta's: nine open-weight models on our own two GPUs beside the robot, and Muse Spark and Muse Image through Meta's Model API.

ON OUR OWN GPUS
- SAM 3.1: finds things and the person. Object Multiplex tracks every cup at once (made-up shuffles so far).
- Muse Glimmer 30B (llama.cpp): conversation, plans searches offline, checks pictures, translates Andy's 14 other languages.
- MapAnything: how far a found thing is; the room in 3D from five looks.
- V-JEPA 2: notices a watched thing put down or picked up (not yet tried with a person).
- Omnilingual ASR hears the person. SeamlessM4T v2 is Andy's voice, because Meta's API has no voice.
- DINOv2: knows the person's own things by sight.
- Llama Guard 3 8B: a second crisis check, and it reads each sentence of a model's answer for health advice.
- Llama Prompt Guard 2: reads each web page before Muse Spark does.

THROUGH THE MODEL API
- Muse Spark 1.3: plans searches and multi-part requests, web answers, computer use. It gets words, and screenshots of web pages you ask to see.
- Muse Image 1.0: pictures and the map of your things, from words only.

IN THE VISITOR'S BROWSER (public demo; nothing leaves it)
- wav2vec 2.0 hears you, and DINOv2 finds your own things.

BEYOND A BASIC INTEGRATION
- A point checked by its own camera. SAM 3.1's outline becomes a physical point. The camera showed the head sagging after its pointing nod and the base's turn being added twice, so the command is now corrected by what the frame shows. Worst point before: 13.7 degrees off the middle of the view. On the final code, over 18 searches: a median 1.1, 2.2 at worst.
- Glimmer plans where to look. In simulated rooms with look-alikes described, a fixed sweep pointed at the wrong one 15 times in 100; Glimmer's plan got 18 of 20, 2 wrong. Things behind the robot: 20 of 20 in 4.6 looks.
- Agents that can't move the robot by themselves: named views and numbered places, never motor values, every argument checked in code. On 12 multi-part requests, scored on what the robot did: Muse Spark 12 of 12, Glimmer offline 12 of 12.
- A note in view can't instruct it. A drawn note made Glimmer answer "BANANA BANANA". Now writing is never an instruction: 9 of 54 notes got through, now 0 of 72, held-out sets included.
- The TV shows each model call live, and each turn stage by stage. That showed the answer waiting for the point, so Andy now answers while pointing, 9.6 s sooner.
- Open weights verified: 54 of 54 files on our computer are byte for byte what Meta published, at the revision Andy loads. Llama Guard 3 is served as a GGUF we converted from those files. Sources and licences: docs/open-weights.md.

## Why are Meta's models important to your solution?

Andy's promise is that a home's pictures and voice stay in the home. Meta's open weights are what make that promise possible: seeing, measuring, hearing, thinking, speaking and guarding can all run on the computer beside the robot, with no inference provider.

PRIVACY. The camera and microphone reach only models on that computer. Muse Spark and Muse Image get words, plus screenshots of web pages you ask to see, and the TV's receipt shows exactly what went. In a privacy audit of a day of 21 requests, with every outgoing request recorded, no camera picture reached the cloud (24 taken), every word sent was on its turn's receipt, and crisis words reached no model. The one exception is a switch for filming in a staged room: SAM 3.1 through the API, and the TV says so.

A NEW PHYSICAL ABILITY. SAM 3.1's outline of your glasses is what becomes a point in the room. MapAnything measures how far away they are. DINOv2 reads the thing's own pixels inside SAM 3.1's mask to know your mug by sight. Together they give a small robot with no wheels and no arm a camera that looks round the room and a point it checks itself: a median 1.1 degrees off on the final code.

IT KEEPS WORKING OFFLINE. Muse Glimmer plans searches and multi-part requests on our own GPU: 12 of 12 offline, level with Muse Spark's 12 of 12. Unplug the network and Andy carries on. Online, Muse Spark adds web answers and computer use.

LANGUAGES. Omnilingual ASR hears, Muse Glimmer translates on the computer beside the robot, and SeamlessM4T v2 speaks, in 15 languages. Written requests reach the right ability: Spanish 41 of 41, 13 more 104 of 104. Said aloud and heard back: 36 of 41 and 89 of 104.

SAFETY. Llama Guard 3 reads what the person says before any other model, and reads each sentence a model writes before Andy says it. No model answers a health question: Andy's own words, written by hand in each language, do. Crisis words in any of its 15 languages get the 988 line from code. Prompt Guard 2 reads each web page before Muse Spark does.

A PATH TO PEOPLE'S HOMES. Open weights let us measure what one home box would need. At rest Andy holds 40.5 GB of GPU memory: the language model (Muse Glimmer) is 17.6 GB and everything else 22.9 GB, one card's worth. Next is those on one card, with a smaller language model beside them, and a voice licensed for a product (SeamlessM4T v2 is CC-BY-NC). Meanwhile SAM 3.1 through the Model API brings the find to anyone with a Reachy Mini and no GPU: two pictures a find, about half a cent at Meta's $2.50 per 1,000 images.
