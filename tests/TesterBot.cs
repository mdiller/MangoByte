using System;
using System.Collections.Generic;
using System.Text;
using System.Threading.Tasks;
using DSharpPlus;
using DSharpPlus.Entities;
using DSharpPlus.EventArgs;

namespace MangoTester
{
  public class TesterBot : DiscordClient
  {
    public TesterBot(DiscordConfiguration config) : base(config) { }

    public async Task Initialize()
    {
      await ConnectAsync();
    }
  }
}
