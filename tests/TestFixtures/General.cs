using System.Linq;
using System.Threading.Tasks;
using DSharpPlus;
using MangoTester;
using NUnit.Framework;

namespace MangoTester.TestFixtures
{
  public class General : BaseTestFixture
  {
    [Test]
    [TestCaseSource(typeof(TestCaseBuilder), nameof(TestCaseBuilder.GetTestCases))]
    public async Task GeneratedTests(string command, string expected)
    {
      await Bot.SendMessageAsync(Channel, command);

      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Reddit()
    {
      await Bot.SendMessageAsync(Channel, "?reddit");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Showerthought()
    {
      await Bot.SendMessageAsync(Channel, "?showerthought");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Help()
    {
      await Bot.SendMessageAsync(Channel, "?help");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Ask()
    {
      await Bot.SendMessageAsync(Channel, "?ask");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
    }

    [Test]
    public async Task Ping4()
    {
      await Bot.SendMessageAsync(Channel, "?ping 4");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
      Assert.That(message.Content, Is.EqualTo("pong pong pong pong"));
    }

    [Test]
    public async Task Insult()
    {
      await Bot.SendMessageAsync(Channel, "?insult");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
    }

    [Test]
    public async Task UserConfig()
    {
      await Bot.SendMessageAsync(Channel, "?userconfig");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task RandomNumber()
    {
      await Bot.SendMessageAsync(Channel, "?random_number 1 10");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
      Assert.That(int.Parse(message.Content), Is.InRange(1, 10), "returned value should be in the expected range");
    }

    [Test]
    public async Task Choose()
    {
      await Bot.SendMessageAsync(Channel, "?choose red blue green");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
      Assert.That(message.Content, Is.AnyOf("red", "blue", "green"));
    }

    [Test]
    public async Task Docs()
    {
      await Bot.SendMessageAsync(Channel, "?docs matchfilter");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Donate()
    {
      await Bot.SendMessageAsync(Channel, "?donate");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Echo()
    {
      await Bot.SendMessageAsync(Channel, "?echo example thing");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
      Assert.That(message.Content, Is.EqualTo("example thing"), "message should return text");
    }

    [Test]
    public async Task Changelog()
    {
      await Bot.SendMessageAsync(Channel, "?changelog");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Info()
    {
      await Bot.SendMessageAsync(Channel, "?info");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Invite()
    {
      await Bot.SendMessageAsync(Channel, "?invite");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
    }

    [Test]
    public async Task BotStats()
    {
      await Bot.SendMessageAsync(Channel, "?botstats");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Lasagna()
    {
      await Bot.SendMessageAsync(Channel, "?lasagna");
      var message = await WaitForMessage();
      Assert.That(message.HasImage(), "message should return an image");
    }

    [Test]
    public async Task Scramble()
    {
      await Bot.SendMessageAsync(Channel, "?scramble Hello my name is bob");
      var message = await WaitForMessage();
      Assert.That(message.HasContent(), "message should return text");
    }

    [Test]
    public async Task Wiki()
    {
      await Bot.SendMessageAsync(Channel, "?wiki dota2");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }
  }
}