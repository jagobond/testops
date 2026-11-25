// This file is a copy of DemoService.Specs.Controller/Support/TestLogger.cs.
// It has been copied for the sake of the demonstration. So that the different 
// automation targets can be studied independently.

using System;
using DemoService.Web.Models;

// ReSharper disable once CheckNamespace
namespace DemoService.Specs.Support;

public class TestLogger
{
    public void LogCreatedQuestion(QuestionDetailModel questionModel)
    {
        Console.WriteLine($"Question: Title: {questionModel.Title}, Body: {questionModel.Body}, Tags: {string.Join(",", questionModel.Tags)}, Votes: {questionModel.Votes}, AskedBy: {questionModel.AskedBy.Name}");
    }

    public void LogPerformAction(string actionName, object input)
    {
        Console.WriteLine($"Perform {actionName}: Input: {input}");
    }

    public void LogPerformActionFailed(string actionName, Exception exception)
    {
        Console.WriteLine($"Perform {actionName} failed: {exception.Message}");
    }
}