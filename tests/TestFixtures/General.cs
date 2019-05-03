using System.Threading.Tasks;
using DSharpPlus;
using MangoTester;
using NUnit.Framework;

namespace MangoTester.TestFixtures
{
  public class General : MangoTestFixture
  {
    public General() : base(222222) { }

    [Test]
    public async Task Thing()
    {
      var channel = await Bot.GetChannelAsync(234567);
      await Bot.SendMessageAsync(channel, "?recent");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }

    [Test]
    public async Task Thing1()
    {
      var channel = await Bot.GetChannelAsync(234567);
      await Bot.SendMessageAsync(channel, "?recent");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }

    [Test]
    public async Task Thing2()
    {
      var channel = await Bot.GetChannelAsync(234567);
      await Bot.SendMessageAsync(channel, "?recent");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }

    [Test]
    public async Task Help()
    {
      var channel = await Bot.GetChannelAsync(234567);
      await Bot.SendMessageAsync(channel, "?help");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }
  }
}