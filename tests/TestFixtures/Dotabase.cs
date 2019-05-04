using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using NUnit.Framework;

namespace MangoTester.TestFixtures
{
  public class Dotabase : BaseTestFixture
  {
    [Test]
    public async Task LastMatch()
    {
      await Bot.SendMessageAsync(Channel, "?lastmatch");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Profile()
    {
      await Bot.SendMessageAsync(Channel, "?profile");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Profile2()
    {
      await Bot.SendMessageAsync(Channel, "?profile");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Profile3()
    {
      await Bot.SendMessageAsync(Channel, "?profile");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }
  }
}
