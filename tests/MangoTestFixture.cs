using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using DSharpPlus;
using NUnit.Framework;

namespace MangoTester
{
  [Parallelizable(ParallelScope.Fixtures)]
  public class MangoTestFixture
  {
    public MangoTestFixture(ulong channelId)
    {
      ChannelId = channelId;
    }

    public ulong ChannelId { get; set; }

    public TesterBot Bot { get; set; }

    [OneTimeSetUp]
    public async Task Setup()
    {
      Bot = new TesterBot(new DiscordConfiguration
      {
        Token = "<token here>",
        TokenType = TokenType.Bot,
        LogLevel = LogLevel.Debug,
        UseInternalLogHandler = true
      });
      await Bot.Initialize();
    }

    [OneTimeTearDown]
    public async Task Teardown()
    {
      await Bot.DisconnectAsync();
    }
  }
}
