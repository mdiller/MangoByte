using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using DSharpPlus;
using DSharpPlus.Entities;
using DSharpPlus.EventArgs;

namespace MangoTester
{
  public class TesterBot : DiscordClient
  {
    public TesterBot(DiscordConfiguration config) : base(config) { }

    public async Task Initialize()
    {
      await ConnectAsync();
    }

    /// <summary>
    /// List of discord message recieved in channels being waited on
    /// </summary>
    public List<DiscordMessage> CaughtMessages { get; set; }

    /// <summary>
    /// Waits for a message in the given channel and times out if no message is recieved in time
    /// </summary>
    /// <param name="channel">channel to wait in</param>
    /// <param name="timeout">timeout in ms</param>
    /// <returns>the message</returns>
    public async Task<DiscordMessage> WaitForMessage(DiscordChannel channel, int timeout = 10000)
    {
      var result = new TaskCompletionSource<DiscordMessage>();

      AsyncEventHandler<MessageCreateEventArgs> thing = e =>
      {
        if (e.Author.Id != this.CurrentUser.Id)
        {
          result.SetResult(e.Message);
        }
        return Task.CompletedTask;
      };

      this.MessageCreated += thing;
      var message = await result.Task;
      this.MessageCreated -= thing;

      return message;
    }
  }
}
