using DSharpPlus.Entities;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MangoTester
{
  public static class ExtensionMethods
  {
    public static bool HasEmbed(this DiscordMessage message)
    {
      return message.Embeds.Count == 1;
    }

    public static bool HasContent(this DiscordMessage message)
    {
      return !string.IsNullOrEmpty(message.Content);
    }

    public static bool HasImage(this DiscordMessage message)
    {
      return message.Attachments.Count == 1;
    }

    /// <summary>
    /// Wait for a process asynchronously
    /// </summary>
    /// <param name="process"></param>
    /// <param name="cancellationToken"></param>
    /// <returns></returns>
    public static Task WaitForExitAsync(this Process process, CancellationToken cancellationToken = default)
    {
      var tcs = new TaskCompletionSource<object>();
      process.EnableRaisingEvents = true;
      process.Exited += (sender, args) => tcs.TrySetResult(null);
      if (cancellationToken != default)
      {
        cancellationToken.Register(tcs.SetCanceled);
      }

      return tcs.Task;
    }
  }
}
