using System;
using System.Linq;
using AwesomeAssertions;
using DemoService.Specs.Support;
using DemoService.Web.Controllers;
using DemoService.Web.Models;

namespace DemoService.Specs.Controller.Drivers;

public class QuestionDetailsPageDriver(QuestionContext questionContext)
{
    public QuestionDetailModel PageContent { get; set; }

    public void LoadPage(Guid? questionId = null)
    {
        var controller = new QuestionController();
        PageContent = controller.GetQuestionDetails(questionId ?? questionContext.CurrentQuestionId);
    }

    public AnswerDetailModel GetAnswerByContentFromPageContent(string content)
    {
        var answer = PageContent.Answers
            .FirstOrDefault(a => a.Content == content);
        answer.Should().NotBeNull();
        return answer;
    }

    public AnswerDetailModel GetAnswerByIdFromPageContent(Guid? answerId = null)
    {
        var id = answerId ?? questionContext.CurrentAnswerId;
        var answer = PageContent.Answers
            .FirstOrDefault(a => a.Id == id);
        answer.Should().NotBeNull();
        return answer;
    }
}