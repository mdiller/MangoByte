using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using DSharpPlus;
using NUnit.Framework;

namespace MangoTester
{
  /// <summary>
  /// Runs before any of the test fixtures start up
  /// Sets up the bot and reads the config file
  /// </summary>
  [SetUpFixture]
  public class MangoSetupFixture
  {
    public static TesterBot Bot { get; private set; }
    public static Config Config { get; private set; }

    /// <summary>
    /// Runs at the beginning of the test to set up the bot and read the config file
    /// </summary>
    [OneTimeSetUp]
    public static async Task MainSetup()
    {
      Config = Config.FromFile("../../../../settings.json");

      Bot = new TesterBot(new DiscordConfiguration
      {
        Token = Config.Token,
        TokenType = TokenType.Bot,
        LogLevel = LogLevel.Debug,
        UseInternalLogHandler = true
      });
      await Bot.Initialize();
    }

    /// <summary>
    /// Disconnects the bot after all the tests have completed
    /// </summary>
    [OneTimeTearDown]
    public static async Task MainTeardown()
    {
      await Bot.DisconnectAsync();
    }
  }
}
