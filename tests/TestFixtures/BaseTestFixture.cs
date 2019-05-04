using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using DSharpPlus;
using DSharpPlus.Entities;
using DSharpPlus.EventArgs;
using NUnit.Framework;

namespace MangoTester.TestFixtures
{
  /// <summary>
  /// The base class for all of the test fixtures
  /// Each one of these is assigned to a channel, and can execute tests independently of the others
  /// </summary>
  [Parallelizable(ParallelScope.Fixtures)]
  public abstract class BaseTestFixture
  {
    /// <summary>
    /// The channel that this test fixture is assigned to
    /// </summary>
    public DiscordChannel Channel { get; set; }

    /// <summary>
    /// The bot
    /// </summary>
    public TesterBot Bot => MangoSetupFixture.Bot;

    /// <summary>
    /// Watches for messages
    /// </summary>
    public EventWatcher<DiscordMessage, MessageCreateEventArgs>  MessageWatcher { get; set; }

    /// <summary>
    /// Sets up this test channel to run tests
    /// </summary>
    [OneTimeSetUp]
    public async Task FixtureSetup()
    {
      var name = this.GetType().Name.ToLower();
      var server = await Bot.GetGuildAsync(MangoSetupFixture.Config.ServerId);
      Channel = server.Channels.FirstOrDefault(c => c.Name == name && c.Type == ChannelType.Text);
      if (Channel == null)
      {
        Channel = await server.CreateChannelAsync(name, ChannelType.Text);
      }

      MessageWatcher = new EventWatcher<DiscordMessage, MessageCreateEventArgs>(e =>
      {
        return e.Author.Id != Bot.CurrentUser.Id && e.Message.Channel.Id == Channel.Id ? e.Message : null;
      });
      Bot.MessageCreated += MessageWatcher.Handler;
    }

    /// <summary>
    /// Cleans up after all the tests have been run
    /// </summary>
    [OneTimeTearDown]
    public void FixtureTeardown()
    {
      Bot.MessageCreated -= MessageWatcher.Handler;
    }

    /// <summary>
    /// Waits for the next message in this test fixture's channel
    /// </summary>
    /// <returns>The message recieved</returns>
    public async Task<DiscordMessage> WaitForMessage(int timeout = 20000)
    {
      return await MessageWatcher.Retrieve(timeout);
    }
  }
}
