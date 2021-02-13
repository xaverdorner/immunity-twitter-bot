# How many days to herd immunity – a twitter bot

<img src="https://github.com/xaverdorner/immunity-twitter-bot/blob/master/twitter_bot_flowchart.png" width="750">

The [Immunity Monitor Twitter bot](https://twitter.com/CImmunitaet) posts a daily estimate of how many days are left until herd immunity is reached in Germany.

The bot goes through 4 steps:
1. downloading the newest vaccination data from rki.de (requests)
2. calculating a 7 days rolling average of the vaccination numbers (pandas)
3. generating a graph based on the calculated numbers (matplotlib)
4. publishing the graph to twitter (tweepy, Google Cloud Console)


<img src="https://github.com/xaverdorner/immunity-twitter-bot/blob/master/example_graph.png" width="750">
