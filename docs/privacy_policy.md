# Mangobyte's Privacy Policy
The purpose of this privacy policy is to describe what data mangobyte collects, how that data is stored, who has access to the data, when the data is deleted, etc. If you have any questions about this or think that something is missing from here, head on over to the [Mangobyte Help Server](https://discord.gg/d6WWHxx) and let me know!

### Terms
For the remainder of this document keep in mind the following:
- "I" or "me" refers to Malcolm Diller (aka [@mdiller](https://github.com/mdiller/) or "@Bilbo's Last Clean Doily" on discord), the person writing this privacy policy, who is the sole developer of mangobyte.
- "mangobyte" refers to the verified instance of the bot, who's client_id is 213476188037971968.
- "guild" refers to a discord "guild", which have also been called discord "servers" in the past.
- "user" refers to a discord "user".

### Some Basic Things
Heres some basic things that you should know about what I do with the data mangobyte collects:
- I do not and will never sell your data.
- I do not and will never share your message content with anyone without your explicit consent.

### The kinds of data collected
There are 3 main types of data that mangobyte collects. Note that these categories are described in more depth in the following sections.
- **Configuration Data**: This is data users specifically provide to mangobyte via commands like `/config` or `/userconfig`
- **Statistics Log Data**: This is logged information that gets recorded whenever a user interacts with mangobyte (primarily via tts messages or a slash command)
- **Other Log Data**: This is logged information that contains debug information and message content information

## Configuration Data
This is data users specifically provide to mangobyte via commands like `/config` or `/userconfig`. This data recorded here is explicitly supplied by the user. To delete a setting set by one of the commands, set that setting to the value "clear". This will remove any data you had previously given. ex: `/userconfig steam clear`.

#### What is this data used for?
This data is used by mangobyte's various commands, and to control the behavior of the bot when interacting with the user/guild.

#### How is it stored?
This data is stored on a file on the same secure server that mangobyte runs from.

#### Who has access to it?
I am the only person who has access to this file, but the bot can also read it. Note that much of this data (for example your steam_id) is accessible to anyone who uses the bot, so this data should be considered public.

#### When is it deleted?
This data is never deleted, except when overridden or cleared via the commands outlined above. To reiterate what was said above: To delete a setting set by one of the commands, set that setting to the value "clear". This will remove any data you had previously given. ex: `/userconfig steam clear`.

## Statistics Logging Data
This is logged information that gets recorded whenever a user interacts with mangobyte (primarily via tts messages or a slash command). One important thing to note is that this data does not contain any message content data from discord messages, though it does contain the command data from slash commands.

#### What is this data used for?
This data is used to create the statistics seen in the `/bot stats` command. It is also used by me to create some graphs and charts and metrics to let me know how the bot is doing and who is using what parts of the bot. I also use this data extensively when doing any debugging of errors occuring in the bot. In general this data is used to help me keep the bot running smoothly, and also track how well the bot is doing. Note that I may share results of queries or graphs with other people for debugging or other purposes, but when I do it will always be stripped of all user and guild identifiers, and will never include message content.

#### How is it stored?
It is stored in a [Grafana Loki](https://grafana.com/oss/loki/) log database. The data is securely sent via https to this database and is stored on a secure server.

#### Who has access to it?
I am the only person who has access to the database. The bot has access to it only for use of the `/bot stats` command.

#### When is it deleted?
This is a relatively new system and at the moment I've set the retention period for these logs to be a year. I may extend this in the future as it is useful for looking at historical data of how the bot has behaved.

## Other Log Data
This is logged information that contains debug information and message content information. This includes errors, warnings, and miscellaneous information that the bot records while running. Note that this data includes message-content data from messages sent in a #tts channel. Also note that if you wish for mangobyte to ignore your #tts messages (and also not log them), you can run this command: `/userconfig ignoremytts enable`.

#### What is this data used for?
This data is exclusively used for debugging and analysing behavior of the bot. Note that I may share results of queries on this data with other people for debugging or other purposes, but when I do it will always be stripped of all user and guild identifiers, and will never include message content.

#### How is it stored?
It is stored in a [Grafana Loki](https://grafana.com/oss/loki/) log database. The data is securely sent via https to this database and is stored on a secure server.

#### Who has access to it?
I am the only person who has access to the database. The bot has access to it only for use of the `/bot stats` command.

#### When is it deleted?
This data is deleted 30 days after it is recieved. This is to comply with GDPR and other policies. It may also be manually deleted by me as requested by individual users. If you would like your message content data deleted for any reason, reach out to me (@Bilbo's Last Clean Doily) via the [Mangobyte Help Server](https://discord.gg/d6WWHxx).