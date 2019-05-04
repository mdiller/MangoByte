using System.Threading.Tasks;
using DSharpPlus;
using MangoTester;
using NUnit.Framework;

namespace MangoTester.TestFixtures
{
  public class General : BaseTestFixture
  {
    [Test]
    public async Task Thing()
    {
      await Bot.SendMessageAsync(Channel, "?recent");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Thing1()
    {
      await Bot.SendMessageAsync(Channel, "?recent");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Thing2()
    {
      await Bot.SendMessageAsync(Channel, "?recent");
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
  }
}