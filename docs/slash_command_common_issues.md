<!-- Note that parts of this file are auto-generated, which is why theres some html comment placeholders below -->
# Slash Command Common Issues

This document is for if you're having issues getting slash commands working. If you're wondering why mango is using slash commands at all, or want more info on mango's slash commands, try running `/docs Slash Commands`

## Main Things To Try
These are all things that people have said fixed their problem, so they might be worth a try
- Try verifying `/ping` works via a DM with mango or on the help server first, that way you can make sure the problem is with your server and not mangobyte or your discord app.
- Kick and re-invite Mangobyte (This step solves most people's issues)
  - Make sure you're using the correct/updated <!-- INVITE_LINK_START -->[Invite Link](https://discordapp.com/oauth2/authorize?permissions=314432&scope=bot%20applications.commands&client_id=213476188037971968)<!-- INVITE_LINK_END -->
- Verify that you have permissions to use slash commands on the server (its called "Use Application Commands")
- Wait a few minutes 
  - Sometimes discord takes a bit to recognize that commands are available the first time
  - If you're getting a "This interaction failed" message sometimes, one of the things that could mean is that mangobyte is lagging. I'm working on fixing these timeout issues, but at the moment they're still happening from time to time.
- Try re-inviting Mangobyte via a *desktop computer*, not a phone (this made a difference for at least one person)
- Restart your discord
- Make sure you don't have too many bot integrations! Some people hve reported that you can have too many and then some will stop working. Try removing some of your unused ones and then reinvite mangobyte.

## "It's working for other people on the server but not for me"

If this is happening, then it could be caused by one of 3 things:
1. **Permissions:** There are new permissions settings available for slash commands. Make sure you have the correct permissions to be able to use slash commands on the server. The permission setting is called "Use Application Commands"
2. **Something is wrong with your discord app:** I've seen an issue where someone wasn't able to get slash commands to work anywhere at all, and they eventually had to completely re-install discord to get it to work. 

## "I can see/use some of the commands, but some new ones don't show up"

Discord says that when you add/change slash commands, it can take up to an hour (or in some cases longer) for them to fully update in all servers the bot is connected to. If you can see and use some of the commands, then you should be all set up, and the other commands should be available soon. If after an hour or so you're still missing some, try some of the things mentioned above like reinviting Mangobyte or restarting your discord app.

## "I can see commands show up when I type "/", but then I just send a message instead of a command"

The slash commands system can be tricky to use. Try playing around with it a bit to see how it works. You won't be able to copy-paste commands anymore, you have to actually type out starting with a slash. 

## "I've tried everything above but nothing works!"

If you've tried all of the above then feel free to head over to the [Mangobyte Info](https://discord.gg/d6WWHxx) discord server and say what's going on and I'll try to help as much as I can.