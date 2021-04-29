using Newtonsoft.Json.Linq;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace MangoTester
{
  public static class TestCaseBuilder
  {
    public static List<object[]> GetTestCases()
    {
      var commandspath = @"C:\dev\projects\MangoByte\resource\json\commands.json";
      string text = File.ReadAllText(commandspath);
      var json = JObject.Parse(text);
      return ((JArray)json["commands"])
        .SelectMany(token => (JArray)token["tests"])
        .Select(TestArgsFromInfo)
        .ToList();
    }

    public static object[] TestArgsFromInfo(JToken token)
    {
      return new object[] { token.Value<string>("command"), token.Value<string>("expected") };
    }
  }

  public enum TestCaseExpectation
  {
    // The command response message should have an embed attached to it
    Embed,

    // The command response message should have text content
    Message,

    // The command response should be a checkmark reaction to the original message
    React_Success,

    // The command response message should have a file attached
    React_Success
  }
}
