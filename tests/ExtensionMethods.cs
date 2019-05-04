using DSharpPlus.Entities;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace MangoTester
{
  public static class ExtensionMethods
  {
    public static bool HasEmbed(this DiscordMessage message)
    {
      return message.Embeds.Count == 1;
    }
  }
}
