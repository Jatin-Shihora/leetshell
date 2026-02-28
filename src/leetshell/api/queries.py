USER_STATUS_QUERY = """
query {
    userStatus {
        isSignedIn
        username
    }
}
"""

PROBLEM_LIST_QUERY = """
query problemsetQuestionList(
    $categorySlug: String,
    $limit: Int,
    $skip: Int,
    $filters: QuestionListFilterInput
) {
    problemsetQuestionList: questionList(
        categorySlug: $categorySlug,
        limit: $limit,
        skip: $skip,
        filters: $filters
    ) {
        total: totalNum
        questions: data {
            acRate
            difficulty
            frontendQuestionId: questionFrontendId
            paidOnly: isPaidOnly
            status
            title
            titleSlug
            topicTags {
                name
                slug
            }
        }
    }
}
"""

QUESTION_DETAIL_QUERY = """
query questionData($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        questionId
        questionFrontendId
        title
        titleSlug
        content
        difficulty
        exampleTestcaseList
        codeSnippets {
            lang
            langSlug
            code
        }
        topicTags {
            name
            slug
        }
        hints
        stats
        isPaidOnly
    }
}
"""
