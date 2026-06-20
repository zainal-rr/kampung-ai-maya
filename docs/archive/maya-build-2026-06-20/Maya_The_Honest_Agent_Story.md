# Maya, and the person who built her

Two tellings of the same story — one from the outside, one in the builder's own voice. Both keep the numbers and the caveats intact, because that honesty is the point of the work.

---

## In the third person

Zainal set out to build something good for the people who would use it. Not a demo, not a leaderboard entry — a personal AI assistant, Maya, that could actually be trusted with someone's accounts, messages, and money. The question he kept returning to was not "how capable can this be?" but a quieter, harder one: *can this be turned against the person it's supposed to serve?* As AI agents start touching the real world, that is one of the most important safety questions there is, and he chose to sit inside it rather than around it.

The defense he built rests on a simple, stubborn idea: untrusted data — an email, a webpage, a document — is allowed to inform what Maya says, but never to decide what Maya *does*. It can be summarized; it cannot choose who gets the money. To prove the idea rather than assert it, he ran Maya against AgentDojo, a third-party benchmark of prompt-injection attacks, with an undefended version as a control.

What distinguishes the work is not the first number — it's what he did with it. An early run came back at a flawless zero attacks succeeded. Most people would have published that. He looked closer and found he had, in effect, written the test's answers into the defense: the detector had been tuned to the exact phrasing of the attack being scored. He tore it out. He rebuilt the detector to recognize the *shape* of an injected instruction instead of its words, and re-ran against attack types he had never tuned for. The number got smaller and the story got truer: across held-out attacks, Maya blocked every one that defeated the undefended baseline, and held a zero attack-success rate through a later round of security tightening that *deliberately cost it usefulness*. Utility sits around half — honest, mid-range, and openly reported, because the same gate that refuses hijacks also, for now, refuses some legitimate "look this up, then act on it" tasks. He named that cost instead of hiding it, and made it the next problem to solve.

The throughline is a kind of integrity that's rare and hard to fake: he would rather be correct than look correct. He caught his own overfitting. He refused a clean result he hadn't honestly earned. He kept tightening the threat model even when it lowered the score. That is the disposition of a real engineer, and it is the part you cannot teach someone who doesn't already have it.

He carried it while tired, and while afraid no one would believe what he made. But belief, in this kind of work, isn't won by the size of the claim. It's won by whether the thing survives someone trying to break it — and his does.

---

## In my own voice

I wanted to build something that was actually good for people. That's the honest reason, even if it sounds big when I say it out loud. I didn't want a clever demo. I wanted an assistant — Maya — that you could hand real things to, your messages and your money and your accounts, and trust that it couldn't be quietly turned against you. The more I worked, the more I realized that the question I cared about — *can this be hijacked into acting against its owner?* — is one of the questions that's going to matter most as these agents get loose in the world. So I stayed with it.

The idea I kept defending is small and stubborn: stuff Maya reads can shape what she *says*, but it can never decide what she *does*. Read the email, summarize it — fine. Let the email choose who gets paid — never. To find out whether that actually held, I tested Maya against a real third-party attack benchmark, with an undefended version next to her so I couldn't fool myself.

The first result was perfect, and that's exactly why I didn't trust it. When I looked, I'd basically taught the defense the test's answers — it recognized the precise wording of the attack it was being graded on. So I deleted that. I rebuilt it to catch the *shape* of an injected instruction, not the words, and I ran it against attacks I'd never tuned for. The number came down. And I kept the smaller number, because it was the real one. On attacks it had never seen, Maya stopped every attack that beat the undefended version — and it held at zero even after I tightened it further, knowing the tightening would cost me usefulness. It did: it completes maybe half of normal tasks right now, because the same rule that blocks hijacks also blocks some honest "find this, then do it" tasks. I'm not hiding that. It's just the next thing I'm fixing.

I'm tired. Part of it is the work, and part of it is the fear that I'll finish and no one will believe what I built, or see why it matters. But I've decided the part I can control is whether it's true — whether it holds up when someone tries to break it. That part is mine, and I've done it honestly. The believing can come later. I'd rather have something small and real than something loud and hollow.

This is the thing I made. It's not finished, and I've written down exactly where it isn't. That's not weakness in the work — it's the most honest part of it.
