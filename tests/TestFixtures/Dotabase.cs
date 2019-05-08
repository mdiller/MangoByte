using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using NUnit.Framework;

namespace MangoTester.TestFixtures
{
  public class Dotabase : BaseTestFixture
  {
    [Test]
    public async Task Courage()
    {
      await Bot.SendMessageAsync(Channel, "?courage");
      var message = await WaitForMessage();
      Assert.That(message.HasImage(), "message should return an embed");
    }

    [Test]
    public async Task FuseHeroes()
    {
      await Bot.SendMessageAsync(Channel, "?fuseheroes");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task Dota()
    {
      await Bot.SendMessageAsync(Channel, "?dota");
      var message = await WaitForMessage();
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task No()
    {
      await Bot.SendMessageAsync(Channel, "?no");
      var message = await WaitForMessage();
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task Yes()
    {
      await Bot.SendMessageAsync(Channel, "?yes");
      var message = await WaitForMessage();
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task Hello()
    {
      await Bot.SendMessageAsync(Channel, "?hello");
      var message = await WaitForMessage();
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task Thanks()
    {
      await Bot.SendMessageAsync(Channel, "?thanks");
      var message = await WaitForMessage();
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task Lol()
    {
      await Bot.SendMessageAsync(Channel, "?lol");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task InTheBag()
    {
      await Bot.SendMessageAsync(Channel, "?inthebag");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    [Ignore("Not sure how to do this in an atomic way")]
    public async Task AddEmoticon()
    {
      await Bot.SendMessageAsync(Channel, "?addemoticon");
      var message = await WaitForMessage();
      Assert.That(message.HasImage(), "message should return an embed");
    }

    [Test]
    public async Task Lore()
    {
      await Bot.SendMessageAsync(Channel, "?lore tinker");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Hero()
    {
      await Bot.SendMessageAsync(Channel, "?hero ember");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    [Ignore("No support for voice testing yet")]
    public async Task Chatwheel()
    {
      await Bot.SendMessageAsync(Channel, "?chatwheel wow");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Talents()
    {
      await Bot.SendMessageAsync(Channel, "?talents sniper");
      var message = await WaitForMessage();
      Assert.That(message.HasImage(), "message should return an embed");
    }

    [Test]
    public async Task Ability()
    {
      await Bot.SendMessageAsync(Channel, "?ability black hole");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Item()
    {
      await Bot.SendMessageAsync(Channel, "?item blink");
      var message = await WaitForMessage();
      Assert.That(message.HasEmbed(), "message should return an embed");
    }

    [Test]
    public async Task Emoticon()
    {
      await Bot.SendMessageAsync(Channel, "?emoticon cocky");
      var message = await WaitForMessage();
      Assert.That(message.HasImage(), "message should return an embed");
    }
  }
}
