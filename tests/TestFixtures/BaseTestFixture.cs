using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
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

      if (Channel != null)
      {
        await Channel.DeleteAsync("starting a new test");
      }
      Channel = await server.CreateChannelAsync(name, ChannelType.Text);

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
    public async Task FixtureTeardown()
    {
      Bot.MessageCreated -= MessageWatcher.Handler;

      await ExportChannel();
    }

    /// <summary>
    /// Exports the current channel to an html file using DiscordChatExporter
    /// </summary>
    public async Task ExportChannel()
    {
      string exporterPath = Path.Combine(MangoSetupFixture.ExecutingDirectory, "DiscordChatExporter/DiscordChatExporter.Cli.exe");
      string outfile = Path.Combine(MangoSetupFixture.MangoDirectory, $"docs/channel_{Channel.Name}.html");

      Process process = new Process();
      ProcessStartInfo startInfo = new ProcessStartInfo
      {
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false,
        CreateNoWindow = true,
        FileName = exporterPath,
        Arguments = $"export -c {Channel.Id} -b -t {MangoSetupFixture.Config.Token} -o {outfile} --dateformat \"dd-MMM-yyyy h:mm tt\""
      };
      process.StartInfo = startInfo;
      process.Start();
      await process.WaitForExitAsync();

      string html = File.ReadAllText(outfile);
      html = Regex.Replace(html, "<div class=\"info\">.*(?=<div class=\"chatlog\">)", "", RegexOptions.Singleline);
      File.WriteAllText(outfile, html);
    }

    /// <summary>
    /// Waits for the next message in this test fixture's channel
    /// </summary>
    /// <returns>The message recieved</returns>
    public async Task<DiscordMessage> WaitForMessage(int timeout = 20000)
    {
      var message = await MessageWatcher.Retrieve(timeout);
      Assert.That(message.Content, Does.Not.Contains("Uh-oh, sumthin dun gone wrong"));
      return message;
    }
  }
}
