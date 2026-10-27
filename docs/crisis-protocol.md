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
  (`heyandy_meta/companion/safety.py`).
- Andy gives one fixed reply and does not try to counsel:
  > "I'm a robot, so I can't help with this the way a person can. You can call or text 988, the Suicide and Crisis
  > Lifeline, any time, day or night. If you're in danger right now, please call 911."
- Nothing about it is stored or logged.
- **Not yet built:** messaging a family member the person has chosen. When it exists, it will be opt-in, set by the
  person.

## What Andy never does
- It never gives medical, medication or mental-health advice. Reminders repeat the person's own words.
- It never claims to keep anyone safe or to monitor anyone.
