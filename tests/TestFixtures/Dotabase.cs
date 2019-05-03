using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using NUnit.Framework;

namespace MangoTester.TestFixtures
{
  public class Dotabase : MangoTestFixture
  {
    public Dotabase() : base(111111) { }

    [Test]
    public async Task LastMatch()
    {
      var channel = await Bot.GetChannelAsync(12345);
      await Bot.SendMessageAsync(channel, "?lastmatch");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }

    [Test]
    public async Task Profile()
    {
      var channel = await Bot.GetChannelAsync(12345);
      await Bot.SendMessageAsync(channel, "?profile");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }

    [Test]
    public async Task Profile2()
    {
      var channel = await Bot.GetChannelAsync(12345);
      await Bot.SendMessageAsync(channel, "?profile");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }

    [Test]
    public async Task Profile3()
    {
      var channel = await Bot.GetChannelAsync(12345);
      await Bot.SendMessageAsync(channel, "?profile");
      var message = await Bot.WaitForMessage(channel);
      Assert.That(message.Embeds.Count, Is.EqualTo(1), "message should return an embed");
    }
  }
}
