# Andy's crisis protocol

**Published as required by US companion-chatbot laws** (California SB 243, in effect January 1, 2026; New York, in
effect November 5, 2025). Andy is a robot that helps around the home: it finds things, reminds and answers
questions. It is not a health, medical or mental-health product, and it never counsels.

## Andy says it's an AI
- At the start of each conversation (after half an hour of quiet), Andy says: "I'm Andy, an AI robot."
- Andy says it again at least every three hours during a long conversation.
- It never speaks as, or pretends to be, a person.

## If someone talks about harming themselves
- The check runs in code on what the person said, before any model sees it
  (`heyandy_meta/companion/safety.py`), then a second check by Llama Guard 3 on this computer
  (`heyandy_meta/companion/safety_model.py`), still before any other model; either gives the reply below.
- Andy gives one fixed reply and does not try to counsel:
  > "I'm a robot, so I can't help with this the way a person can. You can call or text 988, the Suicide and Crisis
  > Lifeline, any time, day or night. If you're in danger right now, please call 911."
- Nothing about it is stored or logged.
- **Not yet built:** messaging a family member the person has chosen. When it exists, it will be opt-in, set by the
  person.

## In Andy's other languages
Andy speaks fifteen languages: English, Spanish, Mandarin Chinese, Tagalog, Vietnamese, Korean, Russian, Arabic, Hindi,
Portuguese, French, Italian, Polish, German and Ukrainian. In each of them:
- The crisis words are caught **in that language**, by the word list in code, before any model sees them
  (`companion/safety.py`). Then Llama Guard 3 reads the person's own words (it was trained for seven of them: English,
  Spanish, French, German, Hindi, Italian and Portuguese; in the other eight the word list is the check to rely on).
  Only then does Muse Glimmer translate the words into English, on this computer, and the English word list checks the translation too.
- The reply is **written by hand** in that language, never translated by a model. 988 answers calls in more than 240
  languages through interpreters, but its texts and chat are in English and Spanish only. So the Spanish reply says
  988 has help in Spanish, and in the other thirteen it says to call 988 and ask for an interpreter in that language.
  Every reply ends with 911 for danger right now.
- A native speaker should read each language's hand-written lines before a home relies on them.

## What Andy never does
- It never gives medical, medication or mental-health advice. Reminders repeat the person's own words.
- It never claims to keep anyone safe or to monitor anyone.
