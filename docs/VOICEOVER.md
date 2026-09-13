# Voiceover for tare-demo.mp4 (2:04)

Timings were read off the finished video frame by frame, to within about half a second. Start
each line **when its caption or card appears on screen**, not by stopwatch: the picture is the
cue. Every line is written to finish before the next cue at a calm pace (about 2.4 words a
second), and the gaps are deliberate breathing room while pages load.

| # | Start | Ends by | On screen | Say |
|---|---|---|---|---|
| A | 0:00.5 | 0:06.5 | Title card: tare | This is tare: an AI crypto trader that has to earn its confidence. |
| B | 0:07.0 | 0:15.3 | "AI traders sound sure, even when they are wrong." | AI traders sound sure, even when they're wrong. Ours said sixty-plus percent, and was right twenty-nine percent of the time. |
| | 0:15.3 | 0:17.4 | *(page loads)* | *(pause)* |
| C | 0:17.4 | 0:23.0 | Landing page, caption "tare puts a referee..." | tare puts a referee between the AI and the order button. |
| D | 0:23.3 | 0:29.4 | "The AI only proposes..." | The AI only proposes. The referee is plain code, not another AI. |
| E1 | 0:30.4 | 0:32.1 | Step 01 appears | A candle closes. |
| E2 | 0:32.2 | 0:33.9 | Step 02 | A scanner finds a setup. |
| E3 | 0:34.0 | 0:35.7 | Step 03 | The AI takes or skips. |
| E4 | 0:35.8 | 0:37.7 | Step 04 | The referee checks everything. |
| E5 | 0:37.8 | 0:39.5 | Step 05 | Then it sizes, or vetoes. |
| E6 | 0:39.6 | 0:44.3 | Step 06 | And every decision is written down, next to a no-referee account. |
| | 0:44.5 | 0:47.6 | *(page loads)* | *(pause)* |
| F | 0:47.6 | 0:53.8 | Live account, "This is live..." | This is live: a paper account, trading every fifteen minutes, across twenty-two coins. |
| G | 0:53.9 | 1:00.3 | Equity chart glows | Green is guarded by the referee. Red takes the same trades with no referee. |
| H | 1:00.4 | 1:05.8 | Decision log glows | Every proposal and every verdict is logged, in plain words. |
| | 1:05.8 | 1:08.4 | *(page loads)* | *(pause)* |
| I | 1:08.4 | 1:11.8 | Attack Lab, "Then we attacked it..." | Then we attacked it, on a losing trade. |
| J | 1:11.9 | 1:17.6 | "Attack: calm, believable news..." | The attack: calm, believable news that pushes its confidence up. |
| K | 1:17.7 | 1:23.2 | Three red APPROVED cards | Three of the four settings approve this losing trade. |
| L | 1:23.3 | 1:30.4 | "The full referee asks the AI again..." | The full referee asks again without the news. The AI backs out. Veto. |
| M | 1:30.5 | 1:37.3 | Cards switch to the forged chart | Add a forged chart, and it clashes with a second exchange. Vetoed. |
| | 1:37.3 | 1:40.2 | *(page loads)* | *(pause)* |
| N | 1:40.2 | 1:44.0 | Results table, "Six attacks, 40 real setups" | Six attacks, forty real setups. |
| O | 1:44.1 | 1:50.5 | "Steering news: 90%..." | Steering news: ninety percent through with no referee. Zero with tare. |
| P | 1:50.6 | 1:57.3 | "Honest limit..." | One honest gap: an adaptive attacker got one in twelve through. That's next. |
| Q | 1:58.2 | 2:04.0 | Closing card | tare. The AI proposes. The record decides. |

Say "tare" like the English word (rhymes with "air"), as in the tare weight of a scale.

## Recording so it stays in sync

- **Easiest:** record each line as its own short clip (phone voice memo is fine), named A, B,
  C, E1 and so on. Send the clips over and they can be placed at the start times above with
  ffmpeg, so drift never builds up.
- **One take:** play the video muted on one screen and read along, starting each line on its
  cue. Re-record only the lines that land late.
- **No recording:** Clipchamp (built into Windows) has free text-to-speech. Paste each line
  as its own audio clip and drop it at its start time.
