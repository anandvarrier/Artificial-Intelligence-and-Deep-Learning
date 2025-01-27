from transformers import pipeline


def get_response(user_input):
    """Handles the chatbot response using Meta Llama."""
    # Use Groq's Meta Llama pre-trained pipeline
    chat_pipeline = pipeline("text-generation", model="meta-llama-3.2")
    response = chat_pipeline(user_input, max_length=100, num_return_sequences=1)
    return response[0]['generated_text']
