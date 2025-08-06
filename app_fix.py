            "labels": {
                "profile": "/label/{id}",
                "artists": "/label/{id}/artists", 
                "reviews": "/label/{id}/reviews"
            },
            "reviews": {
                "popular": "/reviews/popular?days={number}"
            }
        }
    })

@app.route('/events', methods=['GET'])