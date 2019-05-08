using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace MangoTester
{
  /// <summary>
  /// Watches an event and collects the items it produces
  /// </summary>
  /// <typeparam name="T">The type of items to collect</typeparam>
  /// <typeparam name="G">The event args</typeparam>
  public class EventWatcher<T, G> : IDisposable
  {
    private Func<G, T> filter;
    private SemaphoreSlim itemLock;
    private Queue<T> items;
    private TaskCompletionSource<T> request;

    /// <summary>
    /// Creates an eventwatcher to watch some events
    /// </summary>
    /// <param name="filter">The filter used to transform event args to the desired object. Returns null if should be filtered out.</param>
    public EventWatcher(Func<G, T> filter)
    {
      this.filter = filter;
      this.itemLock = new SemaphoreSlim(1, 1);
      this.items = new Queue<T>();
      this.request = null;
    }

    /// <summary>
    /// Handles the events from the source
    /// </summary>
    /// <param name="eventArgs">The received event args</param>
    public async Task Handler(G eventArgs)
    {
      var item = filter(eventArgs);
      if (item == null)
      {
        return;
      }
      await itemLock.WaitAsync();
      try
      {
        if (request != null && !request.Task.IsCompleted)
        {
          request.SetResult(item);
        }
        else
        {
          items.Enqueue(item);
        }
      }
      finally
      {
        itemLock.Release();
      }
    }

    public void Dispose()
    {
      throw new NotImplementedException();
    }

    /// <summary>
    /// Gets the next item in the queue or waits for a new one to appear
    /// </summary>
    /// <param name="timeout">How long to wait for before giving up and throwing a timeout exception</param>
    /// <returns>The item we are waiting for</returns>
    public async Task<T> Retrieve(int timeout = 20000)
    {
      await itemLock.WaitAsync();
      CancellationTokenSource canceler;
      try
      {
        if (items.Any())
        {
          return items.Dequeue();
        }
        else
        {
          request = new TaskCompletionSource<T>();
          canceler = new CancellationTokenSource(timeout);
          canceler.Token.Register(() => request.TrySetCanceled(), useSynchronizationContext: false);
        }
      }
      finally
      {
        itemLock.Release();
      }
      var item = await request.Task;
      await itemLock.WaitAsync();
      request = null;
      canceler.Dispose();
      itemLock.Release();
      return item;
    }
  }
}
