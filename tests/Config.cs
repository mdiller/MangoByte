using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace MangoTester
{
  public class Config
  {
    protected Config(JToken json)
    {
      Token = json.Value<string>("token");
      ServerId = json.Value<ulong>("server");
    }

    public string Token { get; }
    public ulong ServerId { get; }

    public static Config FromFile(string filename)
    {
      string text = File.ReadAllText(filename);
      var json = JObject.Parse(text);
      return new Config(json["tester"]);
    }
  }
}
